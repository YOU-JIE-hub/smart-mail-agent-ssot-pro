#!/usr/bin/env bash
set -Eeo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PORT_PREF="${PORT:-8000}"
choose_port(){ ss -ltn 2>/dev/null | grep -q ":${PORT_PREF}\b" && { echo "$PORT_PREF"; return; }
  ss -ltn 2>/dev/null | grep -q ":8088\b" && { echo 8088; return; } || echo "$PORT_PREF"; }
USE_PORT="$(choose_port)"; export USE_PORT
python - <<'PY'
import json, urllib.request, os
base=f"http://127.0.0.1:{os.environ['USE_PORT']}"
def post(p, d):
    r=urllib.request.Request(base+p, data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return urllib.request.urlopen(r, timeout=12).read().decode()
print("[E2E] base=", base)
print(post("/classify", {"texts":["我要報價 120000 並請客服協助"], "route":"ml"})[:200])
print(post("/extract", {"text":"請報價 $120000，聯絡 0912345678"})[:200])
PY
echo "[OK] e2e_smoke on PORT=$USE_PORT"
