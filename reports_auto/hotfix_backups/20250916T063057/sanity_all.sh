#!/usr/bin/env bash
set -Eeo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR"
PORT_PREF="${PORT:-8000}"

choose_port() {
  if ss -ltn 2>/dev/null | grep -q ":${PORT_PREF}\b"; then
    echo "$PORT_PREF"
  elif ss -ltn 2>/dev/null | grep -q ":8088\b"; then
    echo 8088
  else
    echo "$PORT_PREF"
  fi
}
USE_PORT="$(choose_port)"; export USE_PORT

python - <<'PY'
import json, os, urllib.request
base=f"http://127.0.0.1:{os.environ['USE_PORT']}"
def do(path, data=None):
    if data is None:
        with urllib.request.urlopen(base+path, timeout=8) as r: return r.read().decode()
    body=json.dumps(data).encode()
    req=urllib.request.Request(base+path, data=body, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=12) as r: return r.read().decode()
print("[GET] /debug/model_meta"); print(do("/debug/model_meta")[:300])
print("[POST] /classify rule"); print(do("/classify",{"texts":["test"],"route":"rule"})[:300])
print("[POST] /classify ml"); print(do("/classify",{"texts":["test"],"route":"ml"})[:300])
print("[POST] /extract"); print(do("/extract",{"text":"請報價 $120000，聯絡 0912345678"})[:300])
PY
echo "[OK] sanity_all on PORT=$USE_PORT"
