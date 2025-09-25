#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT" || exit 2
. .venv/bin/activate 2>/dev/null || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:.sma_tools:${PYTHONPATH:-}"
mkdir -p reports_auto/alignment reports_auto
python - <<'PY'
import json, csv, pathlib
inp = pathlib.Path("reports_auto/silver/intent_silver.jsonl")
out = pathlib.Path("reports_auto/alignment/gold2pred_intent_silver_identity.csv")
out.parent.mkdir(parents=True, exist_ok=True)
n=0
with inp.open(encoding="utf-8", errors="ignore") as f, out.open("w", encoding="utf-8", newline="") as g:
    w = csv.writer(g); w.writerow(["gold_id","pred_id","method","similarity"])
    for ln in f:
        if not ln.strip(): continue
        o=json.loads(ln); i=o.get("id")
        if i: w.writerow([i, i, "identity", "1.0000"]); n+=1
print(f"[WRITE] {out} rows={n}")
PY
python .sma_tools/eval_intent_spam.py --task intent \
  --gold reports_auto/silver/intent_silver.jsonl \
  --pred reports_auto/predict_all.jsonl \
  --map  reports_auto/alignment/gold2pred_intent_silver_identity.csv \
  --out  reports_auto/metrics_intent_silver.txt
echo "[DONE] eval_intent_silver"
