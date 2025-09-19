#!/usr/bin/env bash
set -Eeo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR" reports_auto/api vendor/sma_tools
SERVER_LOG="$ERR_DIR/server.log"; RUN_LOG="$ERR_DIR/run.log"; API_ERR="$ERR_DIR/api.err"; PY_TRACE="$ERR_DIR/py_last_trace.txt"
: >"$SERVER_LOG"; : >"$RUN_LOG"; : >"$API_ERR"; : >"$PY_TRACE"
printf "%s\n%s\n%s\n%s\n" "$SERVER_LOG" "$RUN_LOG" "$API_ERR" "$PY_TRACE" > "$ERR_DIR/where.txt"
set -a; [ -f scripts/env.default ] && . scripts/env.default || true; set +a
export SMA_ERR_DIR="$ERR_DIR"; PORT="${PORT:-8000}"

# 1) 檢查/安裝 FastAPI & uvicorn（OFFLINE=1 時略過）
python - <<'PY' 2>>reports_auto/ERR/api.err || true
import importlib, os, sys, subprocess
def has(m):
    try: importlib.import_module(m); return True
    except Exception: return False
if not (has("fastapi") and has("uvicorn")) and os.environ.get("OFFLINE","0")!="1":
    try:
        subprocess.check_call([sys.executable,"-m","pip","-q","install","fastapi","uvicorn[standard]"])
        print("[INFO] installed fastapi + uvicorn")
    except Exception as e:
        print("[WARN] pip install failed:", e, file=sys.stderr)
PY

# 2) 準備 uvicorn 強制啟動器（若找不到 app 則回退直接 exec 原檔）
cat > vendor/sma_tools/force_uvicorn_runner.py <<'PY'
import os, sys, importlib.util, pathlib, faulthandler
faulthandler.enable(open("reports_auto/ERR/py_last_trace.txt","a"))
path=pathlib.Path(sys.argv[1]); port=int(os.environ.get("PORT","8000"))
spec=importlib.util.spec_from_file_location("sma_api_server_mod", str(path))
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
app=getattr(mod,"app",None)
if app is None and hasattr(mod,"create_app"):
    app=mod.create_app()
if app is None:
    print("[WARN] no app/create_app; raw exec", file=sys.stderr)
    os.execvp(sys.executable,[sys.executable,"-u",str(path)])
else:
    import uvicorn; uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
PY

pick_server_py() {
  [ -f tools/api_server.py ] && { echo tools/api_server.py; return; }
  local c; c="$(ls -1 src/**/api_server.py 2>/dev/null | head -n1 || true)"
  [ -n "$c" ] && echo "$c" || echo ""
}

RUN_DIR="$ROOT/reports_auto/api/$(date +%Y%m%dT%H%M%S)"; mkdir -p "$RUN_DIR"
PIDFILE="$RUN_DIR/api.pid"; OUTLOG="$RUN_DIR/api.out"; ERRLOG="$RUN_DIR/api.err"
CMDLOG="$RUN_DIR/cmdline.txt"; ENVLOG="$RUN_DIR/env.txt"
env | sort > "$ENVLOG"

case "${1:-start}" in
  start)
    SFILE="$(pick_server_py)"
    echo "[PICK] api_server = ${SFILE:-NA}" | tee -a "$RUN_LOG" "$CMDLOG"
    if [ -z "$SFILE" ]; then echo "[FATAL] api_server.py not found" | tee -a "$API_ERR"; exit 86; fi

    # 預編譯檢查語法
    python -m py_compile "$SFILE" 2>>"$API_ERR" || true

    # 清埠 + 背景啟動
    command -v fuser >/dev/null 2>&1 && { fuser -k -n tcp 8000 2>/dev/null || true; fuser -k -n tcp 8088 2>/dev/null || true; }
    ( nohup "$SHELL" -lc "exec python -u vendor/sma_tools/force_uvicorn_runner.py '$SFILE'" >\"$OUTLOG\" 2>\"$ERRLOG\" & echo \$! >\"$PIDFILE\" ) </dev/null >/dev/null 2>&1

    # 等待就緒（先 $PORT 再 8088）
    ok=""
    for i in $(seq 1 60); do ss -ltn 2>/dev/null | grep -q ":${PORT}\b" && { ok="$PORT"; break; }; sleep 0.2; done
    [ -z "$ok" ] && for i in $(seq 1 60); do ss -ltn 2>/dev/null | grep -q ":8088\b" && { ok="8088"; break; }; sleep 0.2; done
    echo "${ok:-NA}" > "$RUN_DIR/actual_port"
    echo "[API] listen=${ok:-NA} pid=$(cat "$PIDFILE" 2>/dev/null || echo NA)" | tee -a "$RUN_LOG"

    [ -n "$ok" ] || { echo "[FATAL] API not listening on $PORT nor 8088" | tee -a "$API_ERR"; exit 87; }
    ;;
  stop)
    [ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE" || true
    command -v fuser >/dev/null 2>&1 && { fuser -k -n tcp 8000 2>/dev/null || true; fuser -k -n tcp 8088 2>/dev/null || true; }
    echo "[*] api_down done"
    ;;
  status)
    ss -ltn 2>/dev/null | grep -E "LISTEN|:${PORT}\b|:8088\b" || true
    ;;
  *)
    echo "usage: $0 {start|stop|status}"; exit 2;;
esac
