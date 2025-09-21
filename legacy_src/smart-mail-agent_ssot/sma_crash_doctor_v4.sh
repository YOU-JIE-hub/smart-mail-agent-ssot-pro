#!/usr/bin/env bash
set -Eeuo pipefail
trap 'ec=$?; echo "[ERR] line:$LINENO cmd:${BASH_COMMAND} (exit=$ec)" >&2; exit $ec' ERR
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT"
. .venv/bin/activate || true
export PYTHONNOUSERSITE=1
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

SUBCMD="${1:-e2e}"; shift || true
CUSTOM_CMD=("$@")

TS="$(date +%Y%m%dT%H%M%S)"
BUNDLES_DIR="reports_auto/crash_bundles"
BUNDLE="${BUNDLES_DIR}/CRASH_${TS}"
LOG_DIR="reports_auto/logs"
STATUS_DIR="reports_auto/status"
ARCHIVE_DIR="reports_auto/archive"
mkdir -p "$BUNDLE" "$LOG_DIR" "$STATUS_DIR" "$ARCHIVE_DIR"

RUN_LOG="${BUNDLE}/run.log"
CMD_TXT="${BUNDLE}/command.txt"
FOCUS="${BUNDLE}/error_focus.txt"

case "$SUBCMD" in
  e2e)
    echo "python -m smart_mail_agent.cli.e2e_safe" > "$CMD_TXT"
    set +e; python -m smart_mail_agent.cli.e2e_safe >"$RUN_LOG" 2>&1; RC=$?; set -e ;;
  tests)
    echo "python -m pytest -q -rA" > "$CMD_TXT"
    set +e; python -m pytest -q -rA >"$RUN_LOG" 2>&1; RC=$?; set -e ;;
  spamcheck)
    echo "python -m smart_mail_agent.spam.spam_filter_orchestrator --text '限時優惠 比特幣 USDT 點此 https://x.y' --sender 'noreply@scam.biz' --threshold 0.6" > "$CMD_TXT"
    set +e; python -m smart_mail_agent.spam.spam_filter_orchestrator --text '限時優惠 比特幣 USDT 點此 https://x.y' --sender 'noreply@scam.biz' --threshold 0.6 >"$RUN_LOG" 2>&1; RC=$?; set -e ;;
  cmd)
    printf "%q " "${CUSTOM_CMD[@]}" > "$CMD_TXT"
    set +e; "${CUSTOM_CMD[@]}" >"$RUN_LOG" 2>&1; RC=$?; set -e ;;
  *) echo "[FATAL] 未知子命令：$SUBCMD" | tee -a "$RUN_LOG"; RC=97 ;;
esac

{
  echo "=== GREP FOCUS ==="
  grep -nE "Traceback|ModuleNotFoundError|ImportError|ERROR|FATAL|No such file|Permission denied|denied|cannot" "$RUN_LOG" || true
  echo
  echo "=== RUN.LOG TAIL (last 200 lines) ==="
  tail -n 200 "$RUN_LOG" 2>/dev/null || true
} > "$FOCUS"

ln -sfn "$(realpath --relative-to="${BUNDLES_DIR}" "${BUNDLE}")" "${BUNDLES_DIR}/LATEST"
tar -czf "reports_auto/archive/CRASH_${TS}.tar.gz" -C "$BUNDLES_DIR" "CRASH_${TS}" || true

echo "[INFO] bundle=${BUNDLE}"
echo "[INFO] focus=${FOCUS}"
echo "[INFO] tarball=reports_auto/archive/CRASH_${TS}.tar.gz"
exit "$RC"
