#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR"
set -a; . scripts/env.default 2>/dev/null || true; set +a
export SMA_INTENT_ML_PKL="${SMA_INTENT_ML_PKL}"
export SMA_RULES_SRC="${SMA_RULES_SRC}"
export SMA_ERR_DIR="$ERR_DIR"
PORT="${PORT:-8000}"
echo "[*] ENV" | tee -a "$ERR_DIR/run.log"
echo "  SMA_INTENT_ML_PKL=$SMA_INTENT_ML_PKL" | tee -a "$ERR_DIR/run.log"
echo "  SMA_RULES_SRC=$SMA_RULES_SRC"         | tee -a "$ERR_DIR/run.log"
echo "  SMA_ERR_DIR=$SMA_ERR_DIR"             | tee -a "$ERR_DIR/run.log"
echo "  PORT=$PORT"                           | tee -a "$ERR_DIR/run.log"
bash scripts/api_down.sh || true
PYBIN="$ROOT/.venv/bin/python"; [ -x "$PYBIN" ] || PYBIN="$(command -v python)"
nohup "$PYBIN" scripts/http_api_min.py >> "$ERR_DIR/server.log" 2>&1 & echo $! > "$ERR_DIR/api.pid"
sleep 0.5
echo "[OK] API ready :$PORT" | tee -a "$ERR_DIR/run.log"
