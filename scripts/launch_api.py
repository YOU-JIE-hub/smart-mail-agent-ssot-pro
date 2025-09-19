import os, subprocess as sp, sys, time, socket, importlib.util
PORT=int(os.environ.get('PORT','8088'))
def exists(p): return os.path.isfile(p)
def is_pkg(mod):
  d=os.path.dirname(mod); return os.path.isfile(os.path.join(d,'__init__.py'))

# 1) 入口優先序：tools/api_server.py -> src/sma/api/server.py -> scripts/api_fallback.py
api_mod=None; run_as_path=None
if exists('tools/api_server.py'):
  if is_pkg('tools/api_server.py'): api_mod='tools.api_server'
  else: run_as_path='tools/api_server.py'
elif exists('src/sma/api/server.py'):
  api_mod='src.sma.api.server'
else:
  # 建最小可用備援
  os.makedirs('scripts', exist_ok=True)
  if not exists('scripts/__init__.py'): open('scripts/__init__.py','w').close()
  if not exists('scripts/api_fallback.py'):
    open('scripts/api_fallback.py','w',encoding='utf-8').write(
      'from fastapi import FastAPI\nfrom pydantic import BaseModel\nimport re,os\napp=FastAPI()\n'
      'class C(BaseModel):\n text:str; route:str="rule"\n' 
      'class E(BaseModel):\n text:str\n' 
      'def meta():\n return {"intent":{"version":os.getenv("SMA_INTENT_VER","legacy"),"training_hash":"(n/a)","metrics":{}},"spam":{"version":"legacy","training_hash":"(n/a)","metrics":{}},"kie":{"version":"legacy","training_hash":"(n/a)","metrics":{}}}\n' 
      '@app.get("/debug/model_meta")\ndef m(): return meta()\n' 
      '@app.post("/classify")\ndef cls(x:C):\n t=x.text.lower(); lab="biz_quote" if ("quote" in t or "報價" in t) else "other"; return {"label":lab,"proba":0.9 if lab=="biz_quote" else 0.6, "route":x.route, "meta":meta()}\n' 
      '@app.post("/extract")\ndef ex(x:E):\n import re; ph=re.findall(r"(?:\+?\d{1,3}[-\s]?)?(?:\d{2,4}[-\s]?)?\d{3,4}[-\s]?\d{3,4}", x.text); am=re.findall(r"\b\d{1,3}(?:,\d{3})*|\b\d+\b", x.text); return {"fields":{"phone":ph[:1] or None, "amount":am[:1] or None}, "meta":meta()}\n' 
    )
  api_mod='scripts.api_fallback'

# 2) 啟動（先釋放埠）
os.system(f'fuser -k -n tcp {PORT} >/dev/null 2>&1 || true')
api_out='reports_auto/api/api.out'; api_err='reports_auto/api/api.err'; pidf='reports_auto/api/api.pid'
cmd=[sys.executable,'-u','-m',api_mod] if api_mod else [sys.executable, run_as_path]
p=sp.Popen(cmd, stdout=open(api_out,'ab'), stderr=open(api_err,'ab'))
open(pidf,'w').write(str(p.pid))

# 3) 健康檢查（最多 20 次，每次 0.2s）
import urllib.request
url=f'http://127.0.0.1:{PORT}/debug/model_meta'
ok=False
for i in range(20):
  try:
    with urllib.request.urlopen(url, timeout=0.5) as resp:
      if resp.status==200: ok=True; break
  except Exception:
    time.sleep(0.2)
print('[launch] mode=', 'module:'+api_mod if api_mod else 'path:'+run_as_path)
print('[launch] health=', ok)
sys.exit(0 if ok else 2)
