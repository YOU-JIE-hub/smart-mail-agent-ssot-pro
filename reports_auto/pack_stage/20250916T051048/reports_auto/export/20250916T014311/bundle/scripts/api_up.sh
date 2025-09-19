#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"; RUN="reports_auto/api/${TS}"
LOG="$RUN/run.log"; ERR="$RUN/api.err"; PY_LAST="$RUN/py_last_trace.txt"
mkdir -p "$RUN" reports_auto/.quarantine; exec > >(tee -a "$LOG") 2>&1
set -a; . scripts/env.default 2>/dev/null || true; set +a; : "${PORT:=8000}"
[ -e .venv ] || { [ -d /home/youjie/projects/smart-mail-agent_ssot/.venv ] && ln -s /home/youjie/projects/smart-mail-agent_ssot/.venv .venv || true; }
PYBIN="$ROOT/.venv/bin/python"
[ -x "$PYBIN" ] || { echo "no venv python: $PYBIN" >"$ERR"; exit 2; }
[ -x scripts/api_down.sh ] && scripts/api_down.sh 2>/dev/null || true
("$PYBIN" scripts/http_api_min.py > "$RUN/server.log" 2>&1 & echo $! > "$RUN/api.pid") || { echo "spawn_failed" > "$ERR"; exit 2; }
echo "[*] DRY_RUN=$SMA_DRY_RUN  PORT=$PORT"; echo "[OK] API ready"
echo "[PATHS]"; echo "  RUN_DIR= $(cd "$RUN"&&pwd)"; echo "  LOG   = $(cd "$RUN"&&pwd)/run.log"; echo "  ERR   = $(cd "$RUN"&&pwd)/api.err"; echo "  PY_LAST= $(cd "$RUN"&&pwd)/py_last_trace.txt"
