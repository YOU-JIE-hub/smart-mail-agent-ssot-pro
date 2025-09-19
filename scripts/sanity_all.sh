#!/usr/bin/env bash
set -Eeo pipefail
ROOT="$HOME/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PORT="${PORT:-8088}"
python - <<PY
import json, urllib.request, os
base=f"http://127.0.0.1:{os.environ.get('PORT','8088')}"
def post(p, d):
    r=urllib.request.Request(base+p, data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return urllib.request.urlopen(r, timeout=12).read().decode()
print("[POST] /classify rule"); print(post("/classify", {"texts":["test"], "route":"rule"})[:200])
print("[POST] /classify ml");   print(post("/classify", {"texts":["test"], "route":"ml"})[:200])
print("[POST] /extract");       print(post("/extract", {"text":"請報價 $120000，聯絡 0912345678"})[:200])
PY
echo "[OK] sanity_all on $PORT"
