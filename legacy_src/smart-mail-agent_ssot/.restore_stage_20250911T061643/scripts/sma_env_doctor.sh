#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"
source .sma_tools/env_guard.sh
guard::at_root
guard::venv_on
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/status/ENV_DOCTOR_${TS}.md"
mkdir -p reports_auto/status reports_auto/logs
{
  echo "# ENV_DOCTOR @ ${TS}"
  echo "## Python"
  python -V
  echo
  echo "## Import checks"
  python - <<'PY'
missing=[]
for m in ["joblib","numpy","yaml","reportlab","requests","bs4","PIL"]:
    try: __import__(m)
    except Exception as e: missing.append(f"{m}:{e}")
print("MISSING:" if missing else "OK", ", ".join(missing) if missing else "none")
PY
  echo
  echo "## Smart-mail-agent modules"
  python - <<'PY'
mods = [
  "smart_mail_agent.utils.logger",
  "smart_mail_agent.utils.config",
  "smart_mail_agent.utils.pdf_safe",
  "smart_mail_agent.spam.spam_filter_orchestrator",
  "smart_mail_agent.rpa.quotation",
  "smart_mail_agent.rpa.policy",
]
for m in mods:
  try:
    __import__(m)
    print(m, "OK")
  except Exception as e:
    print(m, "FAIL", e)
PY
} > "$OUT"
echo "[OK] 體檢輸出: $OUT"
