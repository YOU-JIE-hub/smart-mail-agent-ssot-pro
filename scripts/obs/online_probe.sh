#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
umask 022
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="$ROOT/reports_auto/online/${TS}"
mkdir -p "$OUT" "$ROOT/reports_auto/ERR"
RUNLOG="$OUT/run.log"; : >"$RUNLOG"
PYCODE="$OUT/_probe_client.py"
cat > "$PYCODE" <<'PY'
import os, json, time, traceback
from importlib import import_module
def _import_asgi():
    app = os.getenv("APP","sma.api.app:app")
    for target in (app,"sma.api.service_compat:app"):
        try:
            mod, attr = target.split(":",1)
            return getattr(import_module(mod), attr)
        except Exception:
            continue
    raise RuntimeError("ASGI import failed")
try:
    app = _import_asgi()
except Exception:
    with open(os.path.join(os.environ["OUTDIR"], "probe_exception.txt"), "a", encoding="utf-8") as f:
        traceback.print_exc(file=f)
    raise
client = None
try:
    from fastapi.testclient import TestClient
    client = TestClient(app)
except Exception:
    import httpx
    client = httpx.Client(transport=httpx.ASGITransport(app=app), base_url="http://test")
ENDPOINTS = [
    ("GET","/readyz",None),
    ("GET","/debug/models",None),
    ("POST","/v1/predict/intent",{"text":"hello world"}),
    ("POST","/v1/predict/spam",{"text":"get FREE coupon!!"}),
    ("POST","/v1/predict/kie",{"text":"發票 抬頭 元智大學 金額 NT$1,280 日期 2025-09-01"}),
    ("GET","/v1/kie/health",None),
]
def _dump(name, resp):
    key = name.strip("/").replace("/", "_").replace("-", "_")
    out = os.environ["OUTDIR"]
    with open(os.path.join(out, f"{key}.code"),"w",encoding="utf-8") as f: f.write(str(getattr(resp,"status_code",-1)))
    with open(os.path.join(out, f"{key}.hdr"),"w",encoding="utf-8") as f:
        try:
            for k,v in getattr(resp,"headers",{}).items(): f.write(f"{k}: {v}\n")
        except Exception: pass
    try:
        txt = json.dumps(resp.json(), ensure_ascii=False, indent=2)
    except Exception:
        txt = getattr(resp,"text","")
    with open(os.path.join(out, f"{key}.body"),"w",encoding="utf-8") as f: f.write(txt)
def main():
    out = os.environ["OUTDIR"]
    for method,path,payload in ENDPOINTS:
        t0=time.time()
        try:
            r = client.get(path, timeout=30) if method=="GET" else client.post(path, json=payload, timeout=30)
        except Exception as e:
            class Dummy:
                status_code=599; headers={"X-Probe-Error":e.__class__.__name__}; text=str(e)
                def json(self): raise ValueError("no json")
            r = Dummy()
        _dump(path,r)
        with open(os.path.join(out,"run.log"),"a",encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {method} {path} -> {getattr(r,'status_code',-1)}\n")
if __name__=="__main__":
    os.makedirs(os.environ["OUTDIR"], exist_ok=True); main()
PY
export OUTDIR="$OUT"
python "$PYCODE" || echo "[ERR] probe failed, see $OUT/probe_exception.txt" | tee -a "$RUNLOG"
LATEST="$ROOT/reports_auto/online/latest"; rm -f "$LATEST" && ln -s "$OUT" "$LATEST" 2>/dev/null || true
echo "OUT: $OUT" | tee -a "$RUNLOG"
