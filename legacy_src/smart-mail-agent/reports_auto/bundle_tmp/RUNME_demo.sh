#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
MODEL="$here/$(ls "$here" | grep -E 'model_pipeline\.pkl|text_lr_platt\.pkl' | head -n1)"
THR="$here/ens_thresholds.json"

echo "[INFO] Model = $MODEL"
echo "[INFO] Thr   = $(cat "$THR")"

# 評測任意 JSONL（帶 subject/body/label）
if [[ "${1:-}" == *.jsonl && -f "$1" ]]; then
  DATA="$1"
else
  # 預設回到原 repo 的 test.jsonl（若存在）
  REPO="$(cd "$here/.." && pwd)"
  DATA="$REPO/data/prod_merged/test.jsonl"
  [[ -f "$DATA" ]] || DATA="$REPO/data/spam_sa/test.jsonl"
  [[ -f "$DATA" ]] || DATA="$REPO/data/trec06c_zip/test.jsonl"
fi
echo "[USE] DATA=$DATA"

python - <<'PY'
import os, json, re, joblib
from pathlib import Path
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, roc_auc_score, average_precision_score
from sklearn.pipeline import make_pipeline

HERE=Path(__file__).resolve().parent
PKL = next((p for p in (HERE/"model_pipeline.pkl", HERE/"text_lr_platt.pkl") if p.exists()))
THR = HERE/"ens_thresholds.json"
obj=joblib.load(PKL)
clf=obj if hasattr(obj,"predict_proba") else make_pipeline(obj["vect"], obj["cal"])
cfg=json.loads(THR.read_text()); thr=float(cfg.get("threshold",0.44)); sigmin=int(cfg.get("signals_min",3))

REPO=HERE.parent
cand=[Path(os.environ.get("DATA","")), REPO/"data/prod_merged/test.jsonl", REPO/"data/spam_sa/test.jsonl", REPO/"data/trec06c_zip/test.jsonl"]
DATA=next((p for p in cand if p and p.exists()), None)
assert DATA, "no test jsonl found"

def S(e,k): 
    v=e.get(k,""); 
    return v if isinstance(v,str) else ("" if v is None else str(v))
rows=[json.loads(x) for x in DATA.read_text(encoding="utf-8",errors="ignore").splitlines() if x.strip()]
X=[f"{S(r,'subject')} \n {S(r,'body')}" for r in rows]
y=np.array([1 if r.get("label")=="spam" else 0 for r in rows])

RE_URL=re.compile(r"https?://[^\s)>\]]+",re.I)
SUS_TLD={".zip",".xyz",".top",".cam",".shop",".work",".loan",".country",".gq",".tk",".ml",".cf"}
SUS_EXT={".zip",".rar",".7z",".exe",".js",".vbs",".bat",".cmd",".htm",".html",".lnk",".iso",".docm",".xlsm",".pptm",".scr"}
KW=["重設密碼","驗證","帳戶異常","登入異常","補件","逾期","海關","匯款","退款","發票","稅務","罰款",
    "verify","reset","2fa","account","security","login","signin","update","confirm","invoice","payment","urgent","limited","verify your account"]
def signals(e):
    t=(S(e,"subject")+" "+S(e,"body")).lower()
    urls=RE_URL.findall(t); A=[str(a or "").lower() for a in e.get("attachments",[]) if a]
    s=0
    if urls: s+=1
    if any(u.lower().endswith(tld) for u in urls for tld in SUS_TLD): s+=1
    if any(k in t for k in KW): s+=1
    if any(a.endswith(ext) for a in A for ext in SUS_EXT): s+=1
    if ("account" in t) and any(k in t for k in ("verify","reset","login","signin")): s+=1
    if ("帳戶" in t) and any(k in t for k in ("驗證","重設","登入")): s+=1
    return s

p=clf.predict_proba(X)[:,1]; y_text=(p>=thr).astype(int)
sig=np.array([signals(r) for r in rows]); y_rule=(sig>=sigmin).astype(int)
y_ens=np.maximum(y_text,y_rule)

def rep(tag, y, yhat):
    P,R,F1,_=precision_recall_fscore_support(y,yhat,average=None,labels=[0,1])
    cm=confusion_matrix(y,yhat,labels=[0,1]).tolist()
    return dict(tag=tag, macroF1=(F1[0]+F1[1])/2,
                ham=dict(P=P[0],R=R[0],F1=F1[0]),
                spam=dict(P=P[1],R=R[1],F1=F1[1]), cm=cm)

rt, rr, re = rep("TEXT",y,y_text), rep("RULE",y,y_rule), rep("ENSEMBLE",y,y_ens)
try:
    auc=roc_auc_score(y,p); ap=average_precision_score(y,p)
except: auc=ap=float("nan")
print("[TEXT]", rt)
print("[RULE]", rr)
print("[ENSEMBLE]", re)
print("[AUC ]", round(auc,4), " PR-AUC", round(ap,4))
PY

echo
echo "[INFO] .eml 目錄推論："
echo "  python sma_infer_eml.py <eml_dir> --model \"\$MODEL\" --thresholds \"\$THR\" --out predict_eml.tsv"
