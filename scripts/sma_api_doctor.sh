#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; RUN_LOG="$ERR_DIR/run.log"; mkdir -p "$ERR_DIR"
on_err(){ ec=$?; echo "[API_DOCTOR ERR] ec=$ec" | tee -a "$RUN_LOG"; if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$ERR_DIR")" || true; fi; exit $ec; }
trap on_err ERR
echo "[*] api_down"; bash scripts/api_up_env.sh stop || true
echo "[*] api_up";   bash scripts/api_up_env.sh start
LAST="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
USE_PORT="${PORT:-8000}"; [ -n "$LAST" ] && [ -f "$LAST/actual_port" ] && USE_PORT="$(cat "$LAST/actual_port")"
echo "[*] probe on $USE_PORT"; ss -ltn | grep -E ":${USE_PORT}\b" || { echo "[FATAL] not listening"; exit 90; }
PORT="$USE_PORT" bash scripts/sanity_all.sh
PORT="$USE_PORT" bash scripts/e2e_smoke.sh
echo "[OK] api doctor done on $USE_PORT"
