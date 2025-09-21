#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1
SPAM_PRED="${SPAM_PRED:-artifacts_prod/text_predictions_test.tsv}"
if [ ! -f "$SPAM_PRED" ]; then echo "[FATAL] 找不到預測檔：$SPAM_PRED"; exit 2; fi
export SPAM_PRED
TS="$(date +%Y%m%dT%H%M%S)"; EVADIR="reports_auto/eval/${TS}"
mkdir -p "$EVADIR" "reports_auto/status" "artifacts_prod"
python - <<'PY'
import json, time, os, sys
from pathlib import Path
import pandas as pd, numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, roc_auc_score, average_precision_score
ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)
pred_p=ROOT/os.environ.get("SPAM_PRED","").strip()
if not pred_p.exists(): print(f"[FATAL] 找不到預測檔：{pred_p}"); sys.exit(2)
def load_preds(p):
    try: df=pd.read_csv(p, sep="\t")
    except: df=pd.read_csv(p)
    lower={c.lower():c for c in df.columns}
    s=next((lower[k] for k in("prob_spam","score","prob","pred_score","spam_prob","p_spam","confidence") if k in lower),None)
    y=next((lower[k] for k in("label_true","label","y","target","true","is_spam") if k in lower),None)
    if s is None or y is None: raise RuntimeError(f"欄位不齊: {list(df.columns)}")
    df=df[[s,y]].rename(columns={s:"score",y:"label"}).copy()
    df["label"]=df["label"].map(lambda v: 1 if str(v).strip().lower() in ("1","true","t","yes","y","spam") else 0).astype(int)
    df["score"]=pd.to_numeric(df["score"], errors="coerce").fillna(0.0).clip(0,1); return df
def prf(y_true,score,th):
    pred=(score>=th).astype(int)
    p,r,f1,_=precision_recall_fscore_support(y_true,pred,average="binary",zero_division=0)
    tn,fp,fn,tp=confusion_matrix(y_true,pred).ravel()
    return dict(threshold=float(th),P=float(p),R=float(r),F1=float(f1),TP=int(tp),FP=int(fp),FN=int(fn),TN=int(tn))
df=load_preds(pred_p); y=df["label"].values; s=df["score"].values
ens_p=ROOT/"artifacts_prod/ens_thresholds.json"; curr={}
if ens_p.exists() and ens_p.stat().st_size>0:
    try: curr=json.loads(ens_p.read_text("utf-8"))
    except Exception as e: print(f"[WARN] 讀 ens_thresholds.json 失敗: {e}")
grid=np.linspace(0,1,1001); best=max((prf(y,s,t) for t in grid), key=lambda r:(r["F1"], r["R"]))
row_curr=prf(y,s,float(curr.get("spam", curr.get("threshold",0.5)))) if curr else None
def safe(fn):
    try: return float(fn(y,s))
    except: return float("nan")
auc_roc=safe(roc_auc_score); auc_pr=safe(average_precision_score)
md=[]
md.append("# Spam metrics (auto-cal hotfix v4)")
md.append(f"- preds: {pred_p.as_posix()}"); md.append(f"- rows: {len(df)}")
md.append(f"- ROC-AUC: {auc_roc:.3f}" if np.isfinite(auc_roc) else "- ROC-AUC: N/A")
md.append(f"- PR-AUC: {auc_pr:.3f}" if np.isfinite(auc_pr) else "- PR-AUC: N/A"); md.append("")
md.append("## Best threshold by F1")
md.append(f"- threshold: **{best['threshold']:.3f}**")
md.append(f"- P/R/F1: **{best['P']:.3f}/{best['R']:.3f}/{best['F1']:.3f}**")
md.append(f"- TP/FP/FN/TN: {best['TP']}/{best['FP']}/{best['FN']}/{best['TN']}")
if row_curr is not None:
    md.append("\n## Metrics at current production threshold")
    cur=float(curr.get("spam", curr.get("threshold", 0.5)))
    rc=row_curr; md.append(f"- threshold: **{cur:.3f}**")
    md.append(f"- P/R/F1: **{rc['P']:.3f}/{rc['R']:.3f}/{rc['F1']:.3f}**")
    md.append(f"- TP/FP/FN/TN: {rc['TP']}/{rc['FP']}/{rc['FN']}/{rc['TN']}")
md.append("\n## Suggested production values")
suggest=dict(curr); suggest["spam"]=round(best["threshold"],3)
md.append("```json"); md.append(json.dumps(suggest, ensure_ascii=False, indent=2)); md.append("```")
out=EVADIR/"metrics_spam_autocal_v4.md"; out.write_text("\n".join(md), encoding="utf-8"); print(f"[OK] wrote {out}")
apply=os.environ.get("APPLY","0")=="1"
if apply:
    newj=dict(curr); newj["spam"]=round(best["threshold"],3)
    if ens_p.exists(): ens_p.replace(ens_p.with_suffix(ens_p.suffix+f".bak_{NOW}"))
    (ROOT/"artifacts_prod/ens_thresholds.json").write_text(json.dumps(newj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[APPLY] updated -> artifacts_prod/ens_thresholds.json = {newj}")
else:
    print("[SKIP] 沒有套用（APPLY=1 才會覆蓋 artifacts_prod/ens_thresholds.json）")
status=sorted((ROOT/"reports_auto/status").glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
if status:
    st=status[0]; st.open("a+", encoding="utf-8").write("\n## Spam metrics (auto-cal hotfix v4)\n"+out.read_text("utf-8"))
    print(f"[OK] appended metrics to {st.as_posix()}")
print(f">>> Result => {out.as_posix()}")
PY
