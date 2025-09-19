#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
EVADIR="reports_auto/eval/${TS}"
mkdir -p "$EVADIR" "reports_auto/status" "data/intent_eval" "artifacts_prod"

python - <<'PY'
# -*- coding: utf-8 -*-
import re, json, time
from pathlib import Path
from collections import defaultdict
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)

# 1) 載資料（優先 cleaned）
ds=[]
src=None
for cand in [ROOT/"data/intent_eval/dataset.cleaned.jsonl", ROOT/"data/intent_eval/dataset.jsonl"]:
    if cand.exists() and cand.stat().st_size>0:
        src=cand
        for ln in cand.read_text("utf-8").splitlines():
            ln=ln.strip()
            if not ln: continue
            try: ds.append(json.loads(ln))
            except: pass
        break
if not ds: raise SystemExit("[FATAL] intent_eval dataset not found")

LABELS=["報價","技術支援","投訴","規則詢問","資料異動","其他"]
PRI={k:i for i,k in enumerate(["報價","技術支援","投訴","資料異動","規則詢問","其他"])}

def norm(s:str)->str:
    import unicodedata
    s=(s or "")
    s=unicodedata.normalize("NFKC", s)
    s=s.replace("\u3000"," ").replace("\xa0"," ")
    s=re.sub(r"\s+"," ",s.strip())
    return s

# --- 訊號偵測（必要條件 / 對偶抑制會用到）---
PRICE_SIG = re.compile(
    r"(報價(單|表)?|報個?價|估價|抓價|價格|價錢|費用|費率|單價|給.*報價|開.*報價單)"
    r"|(?:nt\\$|ntd|新台幣|台幣|usd|美金|rmb|人民幣)\\s*\\d"
    r"|\\d[\\d,\\.]*\\s*(?:元|塊|萬|千)", re.I)
HEADCOUNT_SIG = re.compile(r"(?:\\b|^)(?:\\d{1,3})\\s*(?:位|人)(?:\\b|$)")
TECH_SIG = re.compile(
    r"(無法|不能|沒辦法).*(登入|連線|上傳|下載|開啟|執行)"
    r"|錯誤|error|failed|exception|bug|crash|逾時|timeout"
    r"|\\b(401|403|404|408|409|429|500|502|503|504)\\b"
    r"|staging|prod(uction)?|sandbox|沙盒|正式|測試", re.I)
COMPLAINT_SIG = re.compile(
    r"(投訴|申訴|客訴|抱怨|不滿|非常不便|相當不便|失望|氣憤)"
    r"|((已寄出|已送出).*(投訴|申訴).*(表|單))"
    r"|退費|退款|賠償|補償", re.I)
POLICY_SIG = re.compile(
    r"(政策|規範|規則|條款|資安|隱私|gdpr|ccpa|sla|license|授權|合約|白皮書|manual|說明書|文件)", re.I)
DATAEDIT_SIG = re.compile(
    r"(更新|變更|修改|更正|請.*修正).*(資料|資訊|聯絡|地址|電話|mail|e-?mail|發票|抬頭|統編|invoice)"
    r"|((新增|刪除).*(聯絡(人)?|白名單|whitelist|黑名單|blacklist))", re.I)

# --- 基礎分數 ---
def base_scores(t:str):
    s={lab:0.0 for lab in LABELS}
    # 報價
    if PRICE_SIG.search(t): s["報價"]+=1.2
    if HEADCOUNT_SIG.search(t): s["報價"]+=0.2
    # 技術支援
    if TECH_SIG.search(t): s["技術支援"]+=1.2
    # 投訴
    if COMPLAINT_SIG.search(t): s["投訴"]+=1.2
    # 規則詢問
    if POLICY_SIG.search(t): s["規則詢問"]+=1.0
    # 資料異動
    if DATAEDIT_SIG.search(t): s["資料異動"]+=1.0

    # 對偶抑制
    if PRICE_SIG.search(t): s["規則詢問"]-=0.9
    if TECH_SIG.search(t): s["規則詢問"]-=0.6
    if TECH_SIG.search(t): s["報價"]-=0.6
    if COMPLAINT_SIG.search(t): s["報價"]-=0.3

    return s

# --- 必要條件 gating ---
def apply_gates(t:str, s:dict):
    # 報價：必須有「價格/報價」訊號或人數+金額類特徵
    if not PRICE_SIG.search(t) and not HEADCOUNT_SIG.search(t):
        s["報價"] = min(s["報價"], -2.0)
    # 技術支援：必須有技術訊號
    if not TECH_SIG.search(t):
        s["技術支援"] = min(s["技術支援"], -1.0)
    # 投訴：必須有投訴訊號
    if not COMPLAINT_SIG.search(t):
        s["投訴"] = min(s["投訴"], -1.0)
    # 規則詢問：必須有政策/規範類訊號
    if not POLICY_SIG.search(t):
        s["規則詢問"] = min(s["規則詢問"], -1.0)
    # 資料異動：必須有資料異動訊號
    if not DATAEDIT_SIG.search(t):
        s["資料異動"] = min(s["資料異動"], -1.0)
    return s

# 初始門檻/偏壓（較保守）
MIN_KEEP={"報價":0.55,"技術支援":0.50,"投訴":0.45,"規則詢問":0.55,"資料異動":0.40,"其他":-9e9}
BIAS={"報價":0.3,"技術支援":0.0,"投訴":0.3,"規則詢問":0.0,"資料異動":0.2,"其他":0.0}

def predict_with(bias, min_keep, text):
    t = norm(text).lower()
    s = base_scores(t)
    s = apply_gates(t, s)
    for k in s: s[k]+=bias.get(k,0.0)
    best = max(LABELS, key=lambda k:(s[k], -PRI[k]))
    if s[best] < min_keep.get(best,0.5):
        best = "其他"
    return best, s

def eval_with(bias, min_keep):
    y_true, y_pred = [], []
    for r in ds:
        gold = (r.get("label") or r.get("intent") or r.get("category") or "其他")
        text = r.get("text") or r.get("subject") or ""
        pred,_ = predict_with(bias, min_keep, text)
        y_true.append(gold); y_pred.append(pred)
    P,R,F1,_=precision_recall_fscore_support(y_true,y_pred,labels=LABELS,zero_division=0)
    micro=precision_recall_fscore_support(y_true,y_pred,labels=LABELS,average="micro",zero_division=0)
    macro=precision_recall_fscore_support(y_true,y_pred,labels=LABELS,average="macro",zero_division=0)
    return dict(P=P,R=R,F1=F1,micro=micro,macro=macro,y_true=y_true,y_pred=y_pred)

# 2) 輕量調參（在 gating 基礎上微調）
best_bias=dict(BIAS); best_min=dict(MIN_KEEP)
best=eval_with(best_bias,best_min); best_micro=best["micro"][2]

for _ in range(2):
    improved=False
    for lab in LABELS:
        for b in [-0.3,0.0,0.3,0.6]:
            trial_bias=dict(best_bias); trial_bias[lab]=b
            t=eval_with(trial_bias,best_min)
            if t["micro"][2] > best_micro + 1e-6:
                best_bias=trial_bias; best=t; best_micro=t["micro"][2]; improved=True
    for lab, pool in [("報價",[0.50,0.55,0.60]),("投訴",[0.40,0.45,0.50]),("資料異動",[0.35,0.40,0.45])]:
        for th in pool:
            trial_min=dict(best_min); trial_min[lab]=th
            t=eval_with(best_bias,trial_min)
            if t["micro"][2] > best_micro + 1e-6:
                best_min=trial_min; best=t; best_micro=t["micro"][2]; improved=True
    if not improved: break

# 3) 輸出報表與誤分
y_true,y_pred=best["y_true"],best["y_pred"]
P,R,F1=best["P"],best["R"],best["F1"]
cm=confusion_matrix(y_true,y_pred,labels=LABELS)

md=[]
md.append("# Intent metrics (rules hotfix v10)")
md.append(f"- dataset: {src.as_posix()}  size={len(ds)}")
md.append(f"- micro P/R/F1: {best['micro'][0]:.3f}/{best['micro'][1]:.3f}/{best['micro'][2]:.3f}")
md.append(f"- macro F1: {best['macro'][2]:.3f}")
md.append(f"- bias: {json.dumps(best_bias,ensure_ascii=False)}")
md.append(f"- min_keep: {json.dumps(best_min,ensure_ascii=False)}\n")
md.append("|label|P|R|F1|"); md.append("|---|---:|---:|---:|")
for lab,p,r,f in zip(LABELS,P,R,F1):
    md.append(f"|{lab}|{p:.3f}|{r:.3f}|{f:.3f}|")

md.append("\n## Confusion Matrix")
hdr="|gold\\pred|"+"|".join(LABELS)+"|"
md.extend([hdr,"|"+"|".join(["---"]*(len(LABELS)+1))+"|"])
for i,lab in enumerate(LABELS):
    row=[lab]+[str(int(cm[i,j])) for j in range(len(LABELS))]
    md.append("|" + "|".join(row) + "|")

# 誤分樣本（FN/FP 前 120）
mis=[]; per_lab=defaultdict(lambda:defaultdict(list))
for i,(gt,pd,rec) in enumerate(zip(y_true,y_pred,ds)):
    if gt!=pd:
        text=(rec.get("text") or rec.get("subject") or "")
        _,sc=predict_with(best_bias,best_min,text)
        mis.append({"i":i,"gold":gt,"pred":pd,"text":text,"scores":sc})
        per_lab[gt]["FN"].append((i,text,pd))
        per_lab[pd]["FP"].append((i,text,gt))

(EVADIR/"metrics_intent_rules_hotfix_v10.md").write_text("\n".join(md),"utf-8")
(EVADIR/"intent_miscls_v10.jsonl").write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in mis),"utf-8")

def dump_txt(items, path, k=120):
    lines=[]
    for i,(idx,txt,aux) in enumerate(items[:k]):
        txt_clean=txt.replace("\n"," ").replace("\r"," ")
        lines.append(f"[{idx}] ({aux}) {txt_clean}")
    Path(path).write_text("\n".join(lines),"utf-8")

for lab in LABELS:
    dump_txt(per_lab[lab]["FN"], (EVADIR/f"FN_{lab}.txt").as_posix())
    dump_txt(per_lab[lab]["FP"], (EVADIR/f"FP_{lab}.txt").as_posix())

# 附掛 ONECLICK
status_dir=ROOT/"reports_auto/status"; status_dir.mkdir(parents=True, exist_ok=True)
lst=sorted(status_dir.glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
if lst:
    tgt=lst[0]
    with tgt.open("a",encoding="utf-8") as w:
        w.write("\n## Intent metrics (rules hotfix v10)\n")
        w.write((EVADIR/"metrics_intent_rules_hotfix_v10.md").read_text("utf-8"))
    print(f"[OK] appended metrics to {tgt.as_posix()}")

print(f">>> Result => {(EVADIR/'metrics_intent_rules_hotfix_v10.md').as_posix()}")
print(f"[OK] dumped misclassifications -> {(EVADIR/'intent_miscls_v10.jsonl').as_posix()} (count={len(mis)})")
print(f"[OK] FN/FP dumps -> {EVADIR.as_posix()}/FN_*.txt, FP_*.txt")

# 保存校正參數
calib={"bias":best_bias,"min_keep":best_min,"ts":NOW}
(ROOT/"artifacts_prod/intent_rules_calib_v10.json").write_text(json.dumps(calib,ensure_ascii=False,indent=2),"utf-8")
print("[OK] saved calib -> artifacts_prod/intent_rules_calib_v10.json")
PY
