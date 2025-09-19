#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PORT="${PORT:-$(grep -E '^PORT=' scripts/env.default 2>/dev/null | tail -n1 | cut -d= -f2 || echo 8000)}"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR"
{
echo; echo "[*] api_down @ $(date +%Y%m%dT%H%M%S)"; echo "[PATHS]"; echo "  ERR_DIR=$ERR_DIR"
echo "  LOG=$ERR_DIR/run.log"; echo "  ERR=$ERR_DIR/api.err"; echo "  SERVER=$ERR_DIR/server.log"; echo "  PY_LAST=$ERR_DIR/py_last_trace.txt"; echo "  PORT=$PORT"
echo "[*] pre-check listeners on :$PORT"; (command -v ss >/dev/null && ss -lptn "sport = :$PORT" || true) || true
kill_wait(){ local p="${1:-}"; [ -n "$p" ] || return 0; kill "$p" 2>/dev/null || true; for _ in {1..20}; do kill -0 "$p" 2>/dev/null || return 0; sleep 0.1; done; kill -9 "$p" 2>/dev/null || true; }
for pf in reports_auto/api/LAST.pid reports_auto/ERR/api.pid; do [ -f "$pf" ] || continue; pid="$(cat "$pf" 2>/dev/null || true)"; [ -n "$pid" ] && kill_wait "$pid"; rm -f "$pf" || true; done
echo "[*] force-free :$PORT if still occupied"
if command -v fuser >/dev/null 2>&1; then fuser -k "${PORT}"/tcp 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then mapfile -t LP < <(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true); for p in "${LP[@]:-}"; do kill_wait "$p"; done
else mapfile -t SP < <(ss -lptn "sport = :${PORT}" 2>/dev/null | sed -n 's/.*pid=\([0-9]\+\).*/\1/p'); for p in "${SP[@]:-}"; do kill_wait "$p"; done; fi
echo "[*] post-check listeners on :$PORT"; (command -v ss >/dev/null && ss -lptn "sport = :$PORT" || true) || true
echo "[DOWN] port=$PORT; pidfiles cleared; ERR_DIR=$ERR_DIR"; } >> "$ERR_DIR/run.log" 2>&1 || true
