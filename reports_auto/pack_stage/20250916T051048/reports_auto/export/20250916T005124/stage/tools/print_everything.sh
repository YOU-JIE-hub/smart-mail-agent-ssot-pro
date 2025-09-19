#!/usr/bin/env bash
set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/support_bundle/$TS"
mkdir -p "$OUT"
log(){ echo -e "$@"; }

log "===== ENV ====="
python - <<'PY' | tee "$OUT/env_brief.txt"
import os, sys, json
def v(m):
    try:
        mod=__import__(m); return getattr(mod,"__version__","unknown")
    except Exception as e:
        return f"n/a ({type(e).__name__}: {e})"
print(json.dumps({
  "python": sys.version,
  "cwd": os.getcwd(),
  "numpy": v("numpy"),
  "sklearn": v("sklearn"),
  "joblib": v("joblib"),
  "transformers": v("transformers"),
  "torch": v("torch"),
  "env": {k:v for k,v in os.environ.items() if k in ("SMA_INTENT_ML_PKL","KIE_MODEL_DIR","TRANSFORMERS_OFFLINE")}
}, ensure_ascii=False, indent=2))
PY

log "\n===== FILES (top-level) ====="
ls -la | tee "$OUT/ls_root.txt"

log "\n===== CONFIGS ====="
for f in configs/intent_label_map.json tools/orch/policy_engine.py tools/actions/action_bus.py; do
  [ -f "$f" ] && { echo "--- $f"; sed -n '1,120p' "$f"; }
done | tee "$OUT/configs_head.txt"

log "\n===== DB SCHEMA / VIEWS SAMPLE ====="
if [ -f db/sma.sqlite ]; then
  echo ".schema actions" | sqlite3 db/sma.sqlite | tee "$OUT/schema_actions.sql"
  echo ".schema messages" | sqlite3 db/sma.sqlite | tee "$OUT/schema_messages.sql"
  echo "SELECT * FROM v_intent_daily ORDER BY day DESC, n DESC LIMIT 20;" | sqlite3 -json db/sma.sqlite | tee "$OUT/v_intent_daily.json"
  echo "SELECT * FROM v_hitl_rate LIMIT 20;" | sqlite3 -json db/sma.sqlite | tee "$OUT/v_hitl_rate.json"
  echo "SELECT ts,intent,action,status,artifact_path FROM actions ORDER BY id DESC LIMIT 30;" | sqlite3 -json db/sma.sqlite | tee "$OUT/actions_tail.json"
else
  echo "(no db/sma.sqlite)"
fi

log "\n===== TRI (latest) ====="
LATEST_TRI=$(ls -t reports_auto/eval/*/tri_suite.json 2>/dev/null | head -n1 || true)
if [ -n "$LATEST_TRI" ]; then
  echo "$LATEST_TRI"
  sed -n '1,200p' "$LATEST_TRI" | tee "$OUT/tri_latest.json"
else
  echo "(no TRI)"
fi

log "\n===== KIE pred head ====="
if [ -f reports_auto/kie/pred.jsonl ]; then
  head -n 20 reports_auto/kie/pred.jsonl | tee "$OUT/kie_pred_head.jsonl"
else
  echo "(no KIE pred)"
fi

log "\n===== SPAM SUMMARY ====="
if [ -f reports_auto/prod_quick_report.md ]; then
  sed -n '1,40p' reports_auto/prod_quick_report.md | tee "$OUT/spam_summary.md"
else
  echo "(no spam report)"
fi

log "\n===== KIE MODEL DIR ====="
if [ -n "${KIE_MODEL_DIR:-}" ] && [ -d "$KIE_MODEL_DIR" ]; then
  echo "KIE_MODEL_DIR=$KIE_MODEL_DIR"
  ( ls -l "$KIE_MODEL_DIR" ; echo "---"; for f in config.json tokenizer.json special_tokens_map.json sentencepiece.bpe.model; do [ -f "$KIE_MODEL_DIR/$f" ] && { echo "### $f"; sed -n '1,80p' "$KIE_MODEL_DIR/$f"; echo; }; done ) | tee "$OUT/kie_model_head.txt"
else
  echo "(KIE_MODEL_DIR not set or dir missing)"
fi

log "\n===== DONE. Everything also saved to: $OUT ====="
