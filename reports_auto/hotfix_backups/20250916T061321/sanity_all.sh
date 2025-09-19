#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PREF="${PORT:-8000}"
pick_port(){
  python - <<'PY'
import os, subprocess, re
pref=os.environ.get("PORT","8000")
def listens(p):
  try:
    out=subprocess.check_output(["ss","-ltn"], text=True, timeout=2)
    return bool(re.search(rf":{p}\\b", out))
  except Exception:
    return False
print(pref if listens(pref) else ("8088" if listens("8088") else pref))
PY
}
USE="$(PORT="$PREF" pick_port)"
python - <<PY
import json, sys, time, urllib.request, os
base=f"http://127.0.0.1:{os.environ.get('USE','') or '$USE'}"
def req(path, data=None):
    if data is None:
        with urllib.request.urlopen(base+path, timeout=8) as r: return r.read().decode()
    import json as _json
    body=_json.dumps(data).encode()
    req=urllib.request.Request(base+path,data=body,headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=12) as r: return r.read().decode()
print("[GET] /debug/model_meta"); print(req("/debug/model_meta")[:300])
print("[POST] /classify rule"); print(req("/classify",{"texts":["test email"],"route":"rule"})[:300])
print("[POST] /classify ml"); print(req("/classify",{"texts":["test email"],"route":"ml"})[:300])
print("[POST] /extract"); print(req("/extract",{"text":"請報價 $120000，聯絡 0912345678"})[:300])
PY
echo "[OK] sanity_all on PORT=$USE"
