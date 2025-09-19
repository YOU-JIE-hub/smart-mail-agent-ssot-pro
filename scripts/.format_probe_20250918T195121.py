import os, json, traceback, hashlib, inspect, types
from pathlib import Path
import joblib
OUT=Path('reports_auto/status'); OUT.mkdir(parents=True, exist_ok=True)
INTENT=Path(os.environ['INTENT_PKL'])
SPAM=Path(os.environ['SPAM_PKL'])
KIE=Path(os.environ['KIE_WEIGHTS'])
def sha256_head(p,cap=4*1024*1024):
  h=hashlib.sha256(); r=0
  with open(p,'rb') as f:
    while True:
      b=f.read(1048576)
      if not b: break
      h.update(b); r+=len(b)
      if r>=cap: h.update(b'__TRUNCATED__'); break
  return h.hexdigest()
def snap_obj(o):
  info={'type':str(type(o))}
  try: info['module']=inspect.getmodule(o).__name__
  except: pass
  if isinstance(o,dict): info['top_keys']=sorted(list(o.keys()))[:64]
  # sklearn hints
  for a in ('steps','classes_','n_features_in_','feature_names_in_','best_estimator_'):
    if hasattr(o,a):
      v=getattr(o,a)
      if a=='steps': info['steps']=[n for n,_ in (v or [])]
      elif a=='best_estimator_': info['best_estimator_type']=str(type(v))
      else:
        try: info[a] = int(v) if isinstance(v,int) else (len(v) if hasattr(v,'__len__') else str(type(v)))
        except: info[a]=str(type(v))
  return info
def safe_load(p):
  import sys
  for _ in range(16):
    try: return joblib.load(p)
    except Exception as e:
      msg=''.join(traceback.format_exception_only(type(e),e))
      # 缺模組/類時，建空殼讓 joblib 能走過去（只為讀格式，不做推論）
      import re
      m1=re.search(r"No module named '([^']+)'",msg)
      m2=re.search(r"Can't get attribute '([^']+)' on <module '([^']+)'",msg)
      if m1:
        mod=m1.group(1); M=types.ModuleType(mod); sys.modules[mod]=M; exec('class _Shim: pass', M.__dict__); continue
      if m2:
        cls,mod=m2.group(1),m2.group(2); M=sys.modules.get(mod) or types.ModuleType(mod); sys.modules[mod]=M; exec(f'class {cls}: pass', M.__dict__); continue
      raise
def write(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),'utf-8')
# ---- Intent ----
irep={'path':INTENT.as_posix(),'exists':INTENT.exists()}
if INTENT.exists():
  irep['sha256_head']=sha256_head(INTENT)
  try:
    o=safe_load(INTENT); irep['object']=snap_obj(o)
    # 推斷：是否為文字可直接 predict？（有 steps 且前段像 vectorizer）或需要 numeric features
    steps=irep['object'].get('steps') if isinstance(irep.get('object'),dict) else None
    irep['likely_text_pipeline']=bool(steps)
    irep['likely_numeric_only']=bool(irep['object'].get('n_features_in_',0))
  except Exception as e:
    irep['error']=str(e)[:1000]
write(OUT/f'INTENT_FORMAT_{os.environ.get("TS","TS")}.json', irep)
# ---- Spam ----
srep={'path':SPAM.as_posix(),'exists':SPAM.exists()}
if SPAM.exists():
  srep['sha256_head']=sha256_head(SPAM)
  try:
    o=safe_load(SPAM); srep['object']=snap_obj(o)
    steps=sdep=None
    steps=srep['object'].get('steps') if isinstance(srep.get('object'),dict) else None
    srep['likely_text_pipeline']=bool(steps)
    srep['likely_numeric_only']=bool(srep['object'].get('n_features_in_',0))
  except Exception as e:
    srep['error']=str(e)[:1000]
write(OUT/f'SPAM_FORMAT_{os.environ.get("TS","TS")}.json', srep)
# ---- KIE ----
krep={'path':KIE.as_posix(),'exists':KIE.exists(),'sha256_head': None}
if KIE.exists():
  krep['sha256_head']=sha256_head(KIE)
  b=KIE.parent  # 以你給的 model/ 目錄為準，不去猜其他層
  # 只做存在性檢查，不做任何加載（不裝 torch）
  cand_toks=['tokenizer.json','vocab.json','spiece.model','sentencepiece.bpe.model']
  cand_cfgs=['config.json','config.yaml','config.yml']
  krep['tokenizer_files']=[(b/f).as_posix() for f in cand_toks if (b/f).exists()]
  krep['config_files']=[(b/f).as_posix() for f in cand_cfgs if (b/f).exists()]
write(OUT/f'KIE_FORMAT_{os.environ.get("TS","TS")}.json', krep)
