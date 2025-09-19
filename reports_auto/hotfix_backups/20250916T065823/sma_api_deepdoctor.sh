#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; RUN_LOG="$ERR_DIR/run.log"; mkdir -p "$ERR_DIR"
_open(){ if command -v explorer.exe >/dev/null 2>&1; then explorer.exe "$(wslpath -w "$ERR_DIR")" || true; elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$ERR_DIR" || true; fi; }
on_err(){ ec=$?; echo "[DEEPDOCTOR ERR] ec=$ec" | tee -a "$RUN_LOG"; bash scripts/sma_collect_logs.sh || true; _open; exit $ec; }
trap on_err ERR

# 內建採集器：把所有可能訊息一次印出來
cat > scripts/sma_collect_logs.sh <<'C'
#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"
echo "----- COLLECT $(date '+%F %T') -----"
echo "[PORTS]"; ss -ltnp 2>/dev/null | sed -n '1,200p' || true
echo "[PS] api_server.py"; pgrep -a -f api_server.py || true
LAST="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
if [ -n "$LAST" ]; then
  echo "[RUN_DIR] $LAST"; echo "[actual_port] $(cat "$LAST/actual_port" 2>/dev/null || echo NA)"
  echo "[HEAD api.out]"; sed -n '1,120p' "$LAST/api.out" 2>/dev/null || true
  echo "[HEAD api.err]"; sed -n '1,120p' "$LAST/api.err" 2>/dev/null || true
fi
echo "[TAIL server.log]"; tail -n 200 "$ERR_DIR/server.log" 2>/dev/null || true
echo "[TAIL run.log]"; tail -n 200 "$ERR_DIR/run.log" 2>/dev/null || true
echo "[CAT api.err]"; cat "$ERR_DIR/api.err" 2>/dev/null || true
echo "[TAIL py_last_trace.txt]"; tail -n 200 "$ERR_DIR/py_last_trace.txt" 2>/dev/null || true
C
chmod +x scripts/sma_collect_logs.sh

echo "[*] api_down"; bash scripts/api_up_env.sh stop || true
echo "[*] api_up";   bash scripts/api_up_env.sh start

LAST="$(ls -1dt reports_auto/api/2* 2>/dev/null | head -n1 || true)"
USE="${PORT:-8000}"; [ -n "$LAST" ] && [ -f "$LAST/actual_port" ] && USE="$(cat "$LAST/actual_port")"
echo "[*] using PORT=$USE"
# 初步 smoke
PORT="$USE" bash scripts/sanity_all.sh || true
# e2e
PORT="$USE" bash scripts/e2e_smoke.sh || true

# 無論結果，完整採集一次
bash scripts/sma_collect_logs.sh
echo "[OK] sma_api_deepdoctor done on $USE"
