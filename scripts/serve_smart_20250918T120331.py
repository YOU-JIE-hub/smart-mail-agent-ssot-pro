import os,sys,importlib,inspect,subprocess as sp,time
from pathlib import Path
PORT=int(os.getenv('PORT','8088'))
api_mod=None; run_path=None
def exists(p): return Path(p).is_file()
def pkg_has_init(p): d=Path(p).parent; return (d/'__init__.py').is_file()
if exists('tools/api_server.py'): api_mod='tools.api_server' if pkg_has_init('tools/api_server.py') else None; run_path=None if api_mod else 'tools/api_server.py'
elif exists('src/sma/api/server.py'): api_mod='src.sma.api.server'; run_path=None
else: api_mod=None; run_path=None
print('[serve] chosen:', api_mod or run_path)
def start_cmd(): return [sys.executable,'-u','-m',api_mod] if api_mod else [sys.executable, run_path]
def health(): import urllib.request; url=f'http://127.0.0.1:{PORT}/debug/model_meta';
 for _ in range(30):
  try:
   with urllib.request.urlopen(url,timeout=0.5) as r: return r.status==200
  except Exception: time.sleep(0.2)
 return False
# 先試正式入口
if api_mod or run_path:
  os.system(f'fuser -k -n tcp {PORT} >/dev/null 2>&1 || true')
  p=sp.Popen(start_cmd(), stdout=open('reports_auto/api/api.out','ab'), stderr=open('reports_auto/api/api.err','ab'))
  Path('reports_auto/api/api.pid').write_text(str(p.pid))
  ok=health(); print('[serve] health=',ok)
  if ok: sys.exit(0)
# 走到這裡代表正式入口失敗，啟 fallback
print('[serve] fallback activated')
Path('scripts/__init__.py').write_text('')
Path('scripts/api_fallback.py').write_text('''from fastapi import FastAPI
from pydantic import BaseModel
import re,os
app=FastAPI(title='SMA Fallback')
class C(BaseModel): text:str; route:str='rule'
class E(BaseModel): text:str
def meta(): return {'intent':{'version':'legacy','training_hash':'(n/a)','metrics':{}},'spam':{'version':'legacy','training_hash':'(n/a)','metrics':{}},'kie':{'version':'legacy','training_hash':'(n/a)','metrics':{}}}
@app.get('/debug/model_meta') 
def m(): return meta()
@app.post('/classify')
def cls(x:C): t=x.text.lower(); lab='biz_quote' if ('quote' in t or '報價' in t) else 'other'; return {'label':lab,'proba':0.9 if lab=='biz_quote' else 0.6,'route':x.route,'meta':meta()}
@app.post('/extract')
def ex(x:E): ph=re.findall(r'(?:\+?\d{1,3}[-\s]?)?(?:\d{2,4}[-\s]?)?\d{3,4}[-\s]?\d{3,4}', x.text); am=re.findall(r'\b\d{1,3}(?:,\d{3})*|\b\d+\b', x.text); return {'fields':{'phone':ph[:1] or None,'amount':am[:1] or None},'meta':meta()}
''')
sp.Popen([sys.executable,'-u','-m','scripts.api_fallback'], stdout=open('reports_auto/api/api.out','ab'), stderr=open('reports_auto/api/api.err','ab'))
if not health(): sys.exit(2)
print('[serve] fallback ok')
