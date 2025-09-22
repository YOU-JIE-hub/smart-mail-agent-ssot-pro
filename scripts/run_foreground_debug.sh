#!/usr/bin/env bash
# 前景除錯；不守護；任何退出必落檔
set -Eeuo pipefail
SELF="${BASH_SOURCE[0]-$0}"
ROOT="$(cd "$(dirname "$SELF")/.." && pwd 2>/dev/null || pwd)"
cd "$ROOT" || { echo "[FATAL] cannot cd $ROOT"; exit 2; }

TS="$(date -u +%Y%m%dT%H%M%S)"
OUTD="reports_auto/serve"; DIAGD="reports_auto/serve/diag"
mkdir -p "$OUTD" "$DIAGD" || true
LOG="$OUTD/uvicorn.$TS.log"
DBG="$DIAGD/debug.$TS.txt"

PORT="${PORT:-8000}"
ENV_FILE="${ENV_FILE:-.env}"

trap 'RC=$?;
  {
    echo "[EXIT] rc=$RC  at $(date -u +%Y-%m-%dT%H:%M:%SZ)";
    echo "== PORT/PROCESS (:${PORT}) =="; ss -lptn "sport = :$PORT" 2>&1 || true;
    echo "== LAST LOG =="; tail -n 200 "$LOG" 2>/dev/null || echo "(no log yet)";
    echo "== DMESG OOM =="; dmesg | grep -i -E "killed process|out of memory" | tail -n 10 || true;
  } >>"$DBG" 2>&1
  echo "[DIAG] wrote $DBG"
' EXIT

{
  echo "[TIME] $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "[PWD]  $(pwd)"
  echo "== PYTHON =="; if [[ -x ./.venv/bin/python ]]; then
    echo "PY: $(realpath ./.venv/bin/python)"; ./.venv/bin/python -V || true; ./.venv/bin/python -m pip -V || true
  else
    echo "[NG] ./.venv/bin/python missing"
  fi
  echo "== UVICORN =="; (./.venv/bin/python -m uvicorn --version || echo "[NG] uvicorn not runnable")
  echo "== ENV FILE ($ENV_FILE) =="; ([[ -f "$ENV_FILE" ]] && sed -n '1,200p' "$ENV_FILE") || echo "(no .env)"
  echo "== MODEL EXISTS? =="; ./.venv/bin/python - <<'PY' || true
import os, json
for k in ("INTENT_PKL","SPAM_PKL"):
    p=os.environ.get(k); print(k, "=", p, "exists=", bool(p and os.path.exists(p)))
try:
    import service.app as app; print("import service.app: OK; has app =", hasattr(app,"app"))
except Exception as e:
    import traceback; print("import service.app: FAIL"); traceback.print_exc()
PY
} >>"$DBG" 2>&1

echo "[RUN] uvicorn :$PORT (log -> $LOG)" | tee -a "$DBG"
# 關鍵：直接重導到檔案，不經過 tee 管線，避免 SIGPIPE 關掉伺服器
PYTHONFAULTHANDLER=1 PYTHONUNBUFFERED=1 \
exec ./.venv/bin/python -m uvicorn service.app:app \
  --env-file "$ENV_FILE" --host 127.0.0.1 --port "$PORT" \
  --log-level debug --access-log >>"$LOG" 2>&1
