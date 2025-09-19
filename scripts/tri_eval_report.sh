#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
OUT="reports_auto/intent_report/$(date +%Y%m%dT%H%M%S)"; mkdir -p "$OUT"
python - <<'PY'
from pathlib import Path; Path("reports_auto/intent_report/LATEST.txt").write_text("macro-F1=?, acc=?\n", encoding="utf-8")
print("[REPORT] wrote reports_auto/intent_report/LATEST.txt")
PY
echo "[OK] tri_eval_report"
