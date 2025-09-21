#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

# 預設就吃 artifacts_prod/text_predictions_test.tsv
: "${SPAM_PRED:=artifacts_prod/text_predictions_test.tsv}"

TS="$(date +%Y%m%dT%H%M%S)"
EVADIR="reports_auto/eval/${TS}"
mkdir -p "$EVADIR" "reports_auto/status" "artifacts_prod"

python - <<'PY'
# -*- coding: utf-8 -*-
import json, time, os, sys, math
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, roc_auc_score, average_precision_score

ROOT   = Path(".")
NOW    = time.strftime("%Y%m%dT%H%M%S")
EVADIR = ROOT / f"reports_auto/eval/{NOW}"
EVADIR.mkdir(parents=True, exist_ok=True)

pred_env = os.environ.get("SPAM_PRED","").strip()
pred_p   = (ROOT/pred_env) if pred_env else None
if not pred_p or not pred_p.exists():
    print(f"[FATAL] 找不到預測檔：{pred_p}")
    sys.exit(2)

def load_preds(p: Path):
    # 讀 TSV（容錯：若 \t 失敗則再試預設分隔）
    try:
        df = pd.read_csv(p, sep="\t")
    except Exception:
        df = pd.read_csv(p)
    # 欄位標準化（忽略大小寫）
    cols = {c.lower(): c for c in df.columns}
    score_col = None
    for k in ("prob_spam","score","prob","pred_score","spam_prob","p_spam","confidence"):
        if k in cols: score_col = cols[k]; break
    label_col = None
    for k in ("label_true","label","y","target","true","is_spam"):
        if k in cols: label_col = cols[k]; break
    if score_col is None: raise RuntimeError("找不到分數欄（prob_spam/score/prob/...）")
    if label_col is None: raise RuntimeError("找不到金標欄（label_true/label/y/...）")

    out = df[[score_col, label_col]].rename(columns={score_col:"score", label_col:"label"}).copy()

    # label 轉 0/1
    def to01(x):
        if pd.isna(x): return 0
        s = str(x).strip().lower()
        if s in ("1","true","t","yes","y","spam"): return 1
        if s in ("0","false","f","no","n","ham"):  return 0
        try: return int(float(s))
        except: return 0
    out["label"] = out["label"].map(to01).astype(int)

    # score 轉浮點（保底裁剪至 [0,1]）
    out["score"] = pd.to_numeric(out["score"], errors="coerce").fillna(0.0).clip(0,1)
    return out

def prf_at_threshold(df, th):
    pred = (df["score"] >= th).astype(int)
    p,r,f1,_ = precision_recall_fscore_support(df["label"], pred, average="binary", zero_division=0)
    tn,fp,fn,tp = confusion_matrix(df["label"], pred).ravel()
    return dict(threshold=float(th), P=float(p), R=float(r), F1=float(f1), TP=int(tp), FP=int(fp), FN=int(fn), TN=int(tn))

df = load_preds(pred_p)
print(f"[OK] loaded preds: {pred_p.as_posix()} rows={len(df)}")

# 讀現行門檻
ens_p = ROOT/"artifacts_prod/ens_thresholds.json"
curr = {}
if ens_p.exists() and ens_p.stat().st_size>0:
    try:
        curr = json.loads(ens_p.read_text("utf-8"))
        print(f"[INFO] current ens_thresholds.json => {curr}")
    except Exception as e:
        print(f"[WARN] 讀取 ens_thresholds.json 失敗：{e}")

# 掃 0~1 找最佳 F1
grid = np.linspace(0,1,1001)
best = max((prf_at_threshold(df, th) for th in grid), key=lambda r: (r["F1"], r["R"]))  # 先比 F1，再比 R
row_curr = prf_at_threshold(df, float(curr.get("threshold", 0.5))) if "threshold" in curr else None

# 曲線指標
auc_roc = roc_auc_score(df["label"], df["score"])
auc_pr  = average_precision_score(df["label"], df["score"])

# 產出報告
md = []
md.append("# Spam metrics (auto-cal hotfix v4)")
md.append(f"- preds: {pred_p.as_posix()}")
md.append(f"- rows: {len(df)}")
md.append(f"- ROC-AUC: {auc_roc:.3f}")
md.append(f"- PR-AUC: {auc_pr:.3f}")
md.append("")
md.append("## Best threshold by F1")
md.append(f"- threshold: **{best['threshold']:.3f}**")
md.append(f"- P/R/F1: **{best['P']:.3f}/{best['R']:.3f}/{best['F1']:.3f}**")
md.append(f"- TP/FP/FN/TN: {best['TP']}/{best['FP']}/{best['FN']}/{best['TN']}")
if row_curr is not None:
    md.append("")
    md.append("## Metrics at current production threshold")
    md.append(f"- threshold: **{float(curr.get('threshold')):.3f}**")
    md.append(f"- P/R/F1: **{row_curr['P']:.3f}/{row_curr['R']:.3f}/{row_curr['F1']:.3f}**")
    md.append(f"- TP/FP/FN/TN: {row_curr['TP']}/{row_curr['FP']}/{row_curr['FN']}/{row_curr['TN']}")

md.append("")
md.append("## Suggested production values")
suggest = dict(curr)
suggest["threshold"] = round(best["threshold"], 3)
md.append("```json")
md.append(json.dumps(suggest, ensure_ascii=False, indent=2))
md.append("```")

out_md = EVADIR/"metrics_spam_autocal_v4.md"
out_md.write_text("\n".join(md), encoding="utf-8")
print(f"[OK] wrote {out_md.as_posix()}")

# 是否套用
apply = os.environ.get("APPLY","0") == "1"
if apply:
    # 備份並只更新 threshold，其他鍵保留
    newj = dict(curr)
    newj["threshold"] = round(best["threshold"], 3)
    if ens_p.exists():
        bak = ens_p.with_suffix(ens_p.suffix+f".bak_{NOW}")
        ens_p.replace(bak)
        print(f"[OK] backup -> {bak.as_posix()}")
    ens_p.write_text(json.dumps(newj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[APPLY] updated -> {ens_p.as_posix()} content={newj}")
else:
    print("[SKIP] 沒有套用（APPLY=1 才會覆蓋 artifacts_prod/ens_thresholds.json）")

# 附掛到 ONECLICK 摘要（若存在）
status = sorted((ROOT/"reports_auto/status").glob("ONECLICK_*"), key=lambda p:p.stat().st_mtime, reverse=True)
if status:
    st = status[0]
    with st.open("a+", encoding="utf-8") as f:
        f.write("\n## Spam metrics (auto-cal hotfix v4)\n")
        f.write(out_md.read_text("utf-8"))
    print(f"[OK] appended metrics to {st.as_posix()}")

print(f">>> Result => {out_md.as_posix()}")
PY
