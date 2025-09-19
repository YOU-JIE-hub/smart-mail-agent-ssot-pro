#!/usr/bin/env python3
from __future__ import annotations
import json, re, numpy as np
from pathlib import Path
from sklearn.metrics import (precision_recall_fscore_support, confusion_matrix,
                             roc_auc_score, average_precision_score, brier_score_loss)
import joblib

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

def load_jsonl(fp):
    rows=[]
    with open(fp,encoding="utf-8") as f:
        for line in f: rows.append(json.loads(line))
    X=[(r.get("subject","")+" \n "+r.get("body","")) for r in rows]
    y=np.array([1 if r.get("label")=="spam" else 0 for r in rows])
    return rows, X, y

def unwrap_model(obj):
    # 直接可預測
    if hasattr(obj, "predict_proba"): return obj
    # 包在 dict 裡
    if isinstance(obj, dict):
        for k in ("model","clf","pipeline","estimator"):
            if k in obj and hasattr(obj[k], "predict_proba"):
                return obj[k]
        # 最後嘗試在 values 裡找有 predict_proba 的
        for v in obj.values():
            if hasattr(v, "predict_proba"): return v
    raise TypeError("Unsupported model format: need an estimator with predict_proba, or a dict containing one under keys {model, clf, pipeline, estimator}")

def metrics(y, yhat):
    P,R,F,_=precision_recall_fscore_support(y,yhat,labels=[0,1],zero_division=0)
    cm=confusion_matrix(y,yhat,labels=[0,1])
    macro=(F[0]+F[1])/2
    return macro,(P[0],R[0],F[0]),(P[1],R[1],F[1]),cm

def ece_score(y_true, prob, n_bins=15):
    bins=np.linspace(0,1,n_bins+1); ece=0.0; N=len(prob)
    for i in range(n_bins):
        lo,hi=bins[i],bins[i+1]
        mask=(prob>=lo)&(prob<hi)
        if not np.any(mask): continue
        acc = (y_true[mask]==1).mean()
        conf= prob[mask].mean()
        ece += (mask.mean()) * abs(acc-conf)
    return float(ece)

def source_of(e):
    i=str(e.get("id",""))
    if i.startswith("trec06c"): return "trec06c"
    if i.startswith("trec07p") or "trec07p" in i: return "trec07p"
    if i.startswith("enron")   or "enron" in i:   return "enron"
    if i.startswith("sa::")    or "publiccorpus" in i: return "spamassassin"
    if i.startswith("S"): return "synth"
    return "unknown"

# ===== main =====
data_fp=Path("data/prod_merged/test.jsonl")
rows,X,y=load_jsonl(data_fp)

raw = joblib.load("artifacts_prod/text_lr_platt.pkl")
clf = unwrap_model(raw)

thr_cfg=json.load(open("artifacts_prod/ens_thresholds.json"))
thr=float(thr_cfg.get("threshold", 0.5)); sig_min=int(thr_cfg.get("signals_min",3))

prob   = clf.predict_proba(X)[:,1]
y_text = (prob>=thr).astype(int)
y_rule = np.array([1 if spam_signals_txt(r.get("subject"),r.get("body"),r.get("attachments"))>=sig_min else 0 for r in rows])
y_ens  = np.where((y_text==1)|(y_rule==1),1,0)

def pack_result(name, yhat):
    macro,ham,spam,cm=metrics(y,yhat)
    return {
      "name":name, "macro":float(macro),
      "hamP":float(ham[0]), "hamR":float(ham[1]), "hamF1":float(ham[2]),
      "spamP":float(spam[0]), "spamR":float(spam[1]), "spamF1":float(spam[2]),
      "cm":cm.tolist()
    }

res_text=pack_result("text-only", y_text)
res_rule=pack_result("rule-only", y_rule)
res_ens =pack_result("ensemble", y_ens)

roc=roc_auc_score(y, prob)
pr =average_precision_score(y, prob)
brier=brier_score_loss(y, prob)
ece=ece_score(y, prob)

# by-source 粗分
sources={}
for r,pi,ti,ei in zip(rows, y_rule, y_text, y_ens):
    s=source_of(r); d=sources.setdefault(s, {"N":0,"rule":0,"text":0,"ens":0,"y":0})
    d["N"]+=1; d["rule"]+=int(pi); d["text"]+=int(ti); d["ens"]+=int(ei); d["y"]+=int(r.get("label")=="spam")

lines=[]
lines.append("# Production Evaluation (prod_merged/test.jsonl)\n")
lines.append(f"- Threshold: **{thr:.2f}**  |  Signals_min: **{sig_min}**")
lines.append(f"- ROC-AUC: **{roc:.4f}**  |  PR-AUC: **{pr:.4f}**  |  Brier: **{brier:.4f}**  |  ECE: **{ece:.4f}**\n")
for r in (res_rule,res_text,res_ens):
    lines.append(f"## {r['name']}")
    lines.append(f"- Macro-F1: **{r['macro']:.4f}**")
    lines.append(f"- Ham P/R/F1: {r['hamP']:.3f}/{r['hamR']:.3f}/{r['hamF1']:.3f}")
    lines.append(f"- Spam P/R/F1: {r['spamP']:.3f}/{r['spamR']:.3f}/{r['spamF1']:.3f}")
    lines.append(f"- Confusion: {r['cm']}\n")

lines.append("## By Source (rough split by id prefix)")
lines.append("| source | N | spam_count | rule_pos | text_pos | ens_pos |")
lines.append("|---|---:|---:|---:|---:|---:|")
for s,d in sorted(sources.items()):
    lines.append(f"| {s} | {d['N']} | {d['y']} | {d['rule']} | {d['text']} | {d['ens']} |")

Path("reports_auto/prod_report.md").write_text("\n".join(lines), encoding="utf-8")

# 簡短摘要印到 stdout 方便你看
print("[SUMMARY] thr=%.2f signals_min=%d ROC-AUC=%.4f PR-AUC=%.4f Brier=%.4f ECE=%.4f"
      % (thr, sig_min, roc, pr, brier, ece))
for r in (res_rule,res_text,res_ens):
    print("[",r["name"],"] Macro-F1=%.4f | hamF1=%.3f | spamR=%.3f | spamF1=%.3f | cm=%s" %
          (r["macro"], r["hamF1"], r["spamR"], r["spamF1"], r["cm"]))
print("[OK] wrote reports_auto/prod_report.md")
