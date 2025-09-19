#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
detect(){
  python - <<'PY'
import subprocess,re
def listens(p):
  try:
    out=subprocess.check_output(["ss","-ltn"], text=True, timeout=2)
    return bool(re.search(rf":{p}\\b", out))
  except Exception: return False
print("8000" if listens("8000") else ("8088" if listens("8088") else "8000"))
PY
}
USE="$(detect)"
python - <<PY
import json, urllib.request, os
base=f"http://127.0.0.1:{os.environ.get('USE','') or '$USE'}"
def post(p, d):
    r=urllib.request.Request(base+p, data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return urllib.request.urlopen(r, timeout=12).read().decode()
print("[E2E] classify→extract→plan→act(dry) base=", base)
print(post("/classify", {"texts":["我要報價 120000 並請客服協助"], "route":"ml"})[:200])
print(post("/extract", {"text":"請報價 $120000，聯絡 0912345678"})[:200])
PY
echo "[OK] e2e_smoke"
