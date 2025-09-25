#!/usr/bin/env bash
source .sma_tools/env_guard.sh
set -euo pipefail

# --- 可調參（依任務成本）---
: "${C_FP:=1}"          # 誤判正常信的成本 (False Positive)
: "${C_FN:=5}"          # 漏判垃圾/釣魚的成本 (False Negative) —— 安全場景常用 FN>>FP
: "${RECALL_MIN:=0.95}" # 目標 spam 召回下限
: "${MODEL_DIR:=artifacts_prod}"
: "${OUT_DIR:=reports_auto}"

python - <<'PY'
from __future__ import annotations
import os, json, math, re, numpy as np
from pathlib import Path
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, roc_auc_score, average_precision_score

# ----------------- 共用：載入文字模型（支援 dict{'vect','cal'}） -----------------
def load_text_estimator(pkl_path: str):
    import joblib
    from sklearn.pipeline import make_pipeline
    obj = joblib.load(pkl_path)
    if hasattr(obj, "predict_proba"):
        return obj
    if isinstance(obj, dict):
        if "vect" in obj and "cal" in obj:
            return make_pipeline(obj["vect"], obj["cal"])
        for v in obj.values():
            if hasattr(v, "predict_proba"):
                return v
    raise TypeError(f"No estimator with predict_proba found in {pkl_path}")

# ----------------- 載入資料 -----------------
def load_jsonl(fp):
    rows=[]
    with open(fp,encoding="utf-8") as f:
        for line in f:
            e=json.loads(line); rows.append(e)
    return rows

def text_of(e): return (e.get("subject","")+" \n "+e.get("body",""))

# ----------------- 規則訊號（與你生產一致） -----------------
RE_URL=re.compile(r"https?://[^\s)>\]]+",re.I)
SUS_TLD={".zip",".xyz",".top",".cam",".shop",".work",".loan",".country",".gq",".tk",".ml",".cf"}
SUS_EXT={".zip",".rar",".7z",".exe",".js",".vbs",".bat",".cmd",".htm",".html",".lnk",".iso",".docm",".xlsm",".pptm",".scr"}
KW=["重設密碼","驗證","帳戶異常","登入異常","補件","逾期","海關","匯款","退款","發票","稅務","罰款",
    "verify","reset","2fa","account","security","login","signin","update","confirm","invoice","payment","urgent","limited","verify your account"]

def spam_signals_txt(subj, body, atts):
    t=(subj or "")+" "+(body or ""); tl=t.lower()
    urls=RE_URL.findall(tl); A=[(a or "").lower() for a in (atts or []) if a]
    sig=0
    if urls: sig+=1
    if any(u.lower().endswith(t) for u in urls for t in SUS_TLD): sig+=1
    if any(k in tl for k in KW): sig+=1
    if any(a.endswith(ext) for a in A for ext in SUS_EXT): sig+=1
    if ("account" in tl) and (("verify" in tl) or ("reset" in tl) or ("login" in tl) or ("signin" in tl)): sig+=1
    if ("帳戶" in tl) and (("驗證" in tl) or ("重設" in tl) or ("登入" in tl)): sig+=1
    return sig

# ----------------- 指標與門檻掃描 -----------------
def prf(y_true, y_pred):
    P,R,F1,_ = precision_recall_fscore_support(y_true, y_pred, average=None, labels=[0,1])
    macro = (F1[0]+F1[1])/2
    cm = confusion_matrix(y_true, y_pred, labels=[0,1])
    return dict(macro=macro, ham=dict(P=P[0],R=R[0],F1=F1[0]), spam=dict(P=P[1],R=R[1],F1=F1[1]), cm=cm.tolist())

def prob_metrics(y, prob):
    try:
        auc = roc_auc_score(y, prob)
        ap  = average_precision_score(y, prob)
    except Exception:
        auc = ap = float("nan")
    # ECE (10 bins)
    bins = np.linspace(0,1,11); idx = np.digitize(prob, bins)-1
    ece=0.0
    for b in range(10):
        m = idx==b
        if m.any():
            conf = prob[m].mean()
            acc  = ( (prob[m]>=0.5).astype(int) == y[m] ).mean()
            ece += prob[m].size/len(prob) * abs(acc-conf)
    return dict(roc_auc=float(auc), pr_auc=float(ap), ece=float(ece))

def sweep_thresholds(y, prob, c_fp=1.0, c_fn=5.0, recall_min=0.95):
    grid=np.round(np.arange(0.05,0.951,0.01),2)
    rows=[]
    for thr in grid:
        pred=(prob>=thr).astype(int)
        cm=confusion_matrix(y, pred, labels=[0,1])
        TN, FP, FN, TP = cm[0,0], cm[0,1], cm[1,0], cm[1,1]
        met=prf(y,pred)
        cost=c_fp*FP + c_fn*FN
        rows.append(dict(thr=float(thr), cost=float(cost), spamR=float(met["spam"]["R"]), macroF1=float(met["macro"]),
                         hamF1=float(met["ham"]["F1"]), spamF1=float(met["spam"]["F1"]),
                         FP=int(FP), FN=int(FN)))
    # 先滿足召回，再取成本最低；若沒有達標，取成本最低
    ok=[r for r in rows if r["spamR"]>=recall_min]
    pick = min(ok, key=lambda r: (r["cost"], -r["macroF1"])) if ok else min(rows, key=lambda r: (r["cost"], -r["macroF1"]))
    return rows, pick

# ----------------- 對抗擾動（模擬繞過） -----------------
def perturb(rows, mode:str):
    out=[]
    for e in rows:
        subj=e.get("subject",""); body=e.get("body","")
        if mode=="hxxp":
            body=re.sub(r"http","hxxp", body, flags=re.I)
            body=body.replace(".","[.]")
        elif mode=="zwj":
            body=re.sub(r"([a-zA-Z])", r"\1\u200d", body)
        elif mode=="homoglyph":
            body=re.sub("paypal","paypaI", body, flags=re.I)  # l -> I
            body=re.sub("account","accοunt", body, flags=re.I) # 拉丁o->希臘ο
        out.append({**e, "subject":subj, "body":body})
    return out

# ----------------- 主程式 -----------------
C_FP=float(os.environ.get("C_FP","1"))
C_FN=float(os.environ.get("C_FN","5"))
RECALL_MIN=float(os.environ.get("RECALL_MIN","0.95"))
MODEL_DIR=Path(os.environ.get("MODEL_DIR","artifacts_prod"))
OUT_DIR=Path(os.environ.get("OUT_DIR","reports_auto")); OUT_DIR.mkdir(parents=True, exist_ok=True)

clf = load_text_estimator(str(MODEL_DIR/"text_lr_platt.pkl"))
thrj = json.loads((MODEL_DIR/"ens_thresholds.json").read_text())
thr0=float(thrj.get("threshold",0.44)); sig_min=int(thrj.get("signals_min",3))

# 自動蒐集可用資料集
cands=[
    ("PROD-TEST", Path("data/prod_merged/test.jsonl")),
    ("SA-TEST",   Path("data/spam_sa/test.jsonl")),
    ("TREC06C",   Path("data/trec06c_zip/test.jsonl")),
    ("SYNTH",     Path("data/spam/test.jsonl")),
    ("SA-BENCH",  Path("data/benchmarks/spamassassin.jsonl")),
]
items=[(name,fp) for name,fp in cands if fp.exists()]

def eval_one(name, rows, tag):
    X=[text_of(e) for e in rows]
    y=np.array([1 if e.get("label")=="spam" else 0 for e in rows])
    prob=clf.predict_proba(X)[:,1]
    pred_text=(prob>=thr0).astype(int)
    sig=np.array([spam_signals_txt(e.get("subject",""),e.get("body",""),e.get("attachments",[])) for e in rows])
    pred_rule=(sig>=sig_min).astype(int)
    pred_ens=np.maximum(pred_text, pred_rule)

    m_text=prf(y,pred_text); m_rule=prf(y,pred_rule); m_ens=prf(y,pred_ens)
    pmet=prob_metrics(y,prob)
    with open(OUT_DIR/f"prof_{tag}.txt","w",encoding="utf-8") as w:
        for title, met in [("TEXT",m_text),("RULE",m_rule),("ENS",m_ens)]:
            w.write(f"[{title}][{name}] macro_f1={met['macro']:.4f}\n")
            w.write(f"[{title}][{name}] ham  P/R/F1 = {met['ham']['P']:.3f}/{met['ham']['R']:.3f}/{met['ham']['F1']:.3f}\n")
            w.write(f"[{title}][{name}] spam P/R/F1 = {met['spam']['P']:.3f}/{met['spam']['R']:.3f}/{met['spam']['F1']:.3f}\n")
            w.write(f"[{title}][{name}] confusion = {met['cm']}\n")
        w.write(f"[PROB][{name}] ROC-AUC={pmet['roc_auc']:.4f} PR-AUC={pmet['pr_auc']:.4f} ECE={pmet['ece']:.4f}\n")

    # 門檻掃描（成本）
    sweep, pick = sweep_thresholds(y, prob, C_FP, C_FN, RECALL_MIN)
    import csv
    with open(OUT_DIR/f"thr_{tag}.tsv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f,delimiter='\t'); w.writerow(["thr","cost","spamR","macroF1","hamF1","spamF1","FP","FN"])
        for r in sweep: w.writerow([r["thr"],r["cost"],r["spamR"],r["macroF1"],r["hamF1"],r["spamF1"],r["FP"],r["FN"]])
    return dict(name=name, tag=tag, text=m_text, rule=m_rule, ens=m_ens, prob=pmet, pick=pick, N=len(rows))

# 原始、釣魚高風險、對抗擾動
summary=[]
for name, fp in items:
    base = load_jsonl(fp)
    # 釣魚子集
    def is_phish(e):
        t=(e.get("subject","")+" "+e.get("body","")).lower()
        return ("http://" in t or "https://" in t) or any(t.endswith(xx) for xx in SUS_TLD) or any(k in t for k in KW)
    phish=[e for e in base if is_phish(e)]
    # 評估：原始
    summary.append(eval_one(name, base, f"{name}_base"))
    # 評估：釣魚
    if phish:
        summary.append(eval_one(name+"-PHISH", phish, f"{name}_phish"))
    # 評估：對抗擾動
    for mode in ("hxxp","zwj","homoglyph"):
        rows_p=perturb(base, mode)
        summary.append(eval_one(name+f"-{mode.upper()}", rows_p, f"{name}_{mode}"))

# 產出總結 Markdown
lines=[]
lines.append("# Professional Eval Report\n")
lines.append(f"- Model dir: `{MODEL_DIR}`  |  threshold={thr0:.2f}  |  signals_min={sig_min}  |  C_FP={C_FP}, C_FN={C_FN}, RecallMin={RECALL_MIN}\n")
for s in summary:
    lines.append(f"## {s['name']}  (N={s['N']})")
    for title,met in [("Text-only",s['text']),("Rule-only",s['rule']),("Ensemble(OR)",s['ens'])]:
        lines.append(f"- **{title}**  Macro-F1 **{met['macro']:.4f}**  |  Ham {met['ham']['P']:.3f}/{met['ham']['R']:.3f}/{met['ham']['F1']:.3f}  |  Spam {met['spam']['P']:.3f}/{met['spam']['R']:.3f}/{met['spam']['F1']:.3f}  |  CM={met['cm']}")
    lines.append(f"- Prob: ROC-AUC {s['prob']['roc_auc']:.4f}  |  PR-AUC {s['prob']['pr_auc']:.4f}  |  ECE {s['prob']['ece']:.4f}")
    p=s['pick']; lines.append(f"- Cost-opt threshold (recall≥{RECALL_MIN}): thr **{p['thr']:.2f}** | cost={p['cost']:.1f} | spamR={p['spamR']:.3f} | macroF1={p['macroF1']:.4f} | (FP={p['FP']}, FN={p['FN']})")
    lines.append(f"- Files: `prof_{s['tag']}.txt`, `thr_{s['tag']}.tsv`  \n")

Path(OUT_DIR/"prof_report.md").write_text("\n".join(lines), encoding="utf-8")
print(f"[OK] wrote {OUT_DIR}/prof_report.md")
PY
