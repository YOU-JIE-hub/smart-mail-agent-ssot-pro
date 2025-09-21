#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[ERR] line:$LINENO cmd:${BASH_COMMAND}"' ERR
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"; [ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"
mkdir -p reports_auto/logs
LOG="reports_auto/logs/patch_intent_contract_$(date +%Y%m%dT%H%M%S).log"

{
  echo "[$(date +%H:%M:%S)] [0/4] DB migrate (llm_calls)"
  python tools/db_migrate_llm_calls.py --db db/sma.sqlite || true

  echo "[$(date +%H:%M:%S)] [1/4] v4 fix"
  bash one_click_intents_contract_v4_fix.sh

  echo "[$(date +%H:%M:%S)] [2/4] Validate contract"
  python tools/validate_intent_contract.py && echo "[VALID] intent_contract.json OK :: $(jq -r '.intents|length' artifacts_prod/intent_contract.json 2>/dev/null || echo '?') intents" || true

  echo "[$(date +%H:%M:%S)] [3/4] Health + LATEST symlink"
  python - <<'PY'
from pathlib import Path, re, os
base = Path("reports_auto/e2e_mail")
runs = sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
run = runs[0] if runs else None
sent = sum(1 for _ in (run/"rpa_out/email_sent").glob("*.eml")) if run else 0
print("[HEALTH] latest run:", run.name if run else "None", "sent=", sent)
if run:
    latest = base/"LATEST"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(run.name)
    print("[HEALTH] LATEST ->", run.name)
PY

  echo "[$(date +%H:%M:%S)] [4/4] Retention cleanup (older than 14d)"
  find reports_auto/e2e_mail -maxdepth 1 -type d -regex '.*/[0-9]{8}T[0-9]{6}' -mtime +14 -exec rm -rf {} + 2>/dev/null || true
  find reports_auto/status -type f -name 'INTENTS_*.md' -mtime +14 -delete 2>/dev/null || true
} | tee -a "$LOG"

echo "[DONE] log -> $LOG"
