import os, json, joblib, hashlib, traceback, types, re
from pathlib import Path
from pprint import pformat
root=Path.cwd()
status=Path('reports_auto/status'); status.mkdir(parents=True, exist_ok=True)
OUT_JSON=status/f'MODEL_PROBE_{os.environ.get("TS","20250918T205154")}.json'
OUT_MD=status/f'MODEL_PROBE_{os.environ.get("TS","20250918T205154")}.md'
INTENT=Path(os.environ['INTENT_PKL']); SPAM=Path(os.environ['SPAM_PKL']); KIE=Path(os.environ['KIE_DIR'])
def sha256_head(p,cap=4*1024*1024):
  h=hashlib.sha256(); r=0
  with open(p,'rb') as f:
    while True:
      b=f.read(1024*1024)
      if not b: break
      h.update(b); r+=len(b)
      if r>=cap: h.update(b'__TRUNCATED__'); break
  return h.hexdigest()
def robust_load(p):
  import sys
  for _ in range(24):
    try: return joblib.load(p)
    except Exception as e:
      et=''.join(traceback.format_exception_only(type(e),e))
      m1=re.search(r"No module named '([^']+)'",et); m2=re.search(r"Can't get attribute '([^']+)' on <module '([^']+)'",et)
      if m1:
        mod=m1.group(1); M=types.ModuleType(mod); sys.modules[mod]=M; exec('class _Shim: pass', M.__dict__); continue
      if m2:
        cls,mod=m2.group(1),m2.group(2); M=sys.modules.get(mod) or types.ModuleType(mod); sys.modules[mod]=M; exec(f'class {cls}: pass', M.__dict__); continue
      raise
def pipe_summary(obj):
  from sklearn.pipeline import Pipeline
  s={'is_pipeline':False,'steps':[],'has_rules_feat':False,'fitted_tail_attrs':[]}
  try:
    if isinstance(obj, Pipeline):
      s['is_pipeline']=True
      for nm,st in obj.steps:
        s['steps'].append({'name':nm,'cls':st.__class__.__name__,'module':getattr(st,'__module__','')})
        mod=getattr(st,'__module__',''); nm2=st.__class__.__name__.lower()
        if ('rules_features' in mod) or ('rules_feat' in nm.lower()) or ('rules_feat' in nm2): s['has_rules_feat']=True
      tail=obj.steps[-1][1]
      s['fitted_tail_attrs']=[a for a in ('classes_','coef_','n_features_in_','feature_log_prob_') if hasattr(tail,a)]
  except Exception: pass
  return s
def inspect_pkl(p):
  out={'path':p.as_posix(),'exists':p.exists()}
  if not p.exists(): return out
  out['sha256_head']=sha256_head(p)
  try:
    o=robust_load(p); out['type']=type(o).__name__
    if isinstance(o, dict):
      out['keys']=list(o.keys())
      cand=o.get('pipeline') or o.get('sk') or o.get('pipe') or o.get('model_pipeline')
      out['candidate']=type(cand).__name__ if cand is not None else None
      out['pipeline_summary']=pipe_summary(cand) if cand is not None else None
    else:
      out['pipeline_summary']=pipe_summary(o)
  except Exception as e:
    out['load_error']=str(e)
  return out
def inspect_kie(d):
  d=Path(d); out={'dir':d.as_posix(),'exists':d.exists()}
  if not d.exists(): return out
  files=sorted([x.name for x in d.glob('*')])
  out['files']=files
  for f in ('model.safetensors','tokenizer.json','sentencepiece.bpe.model','vocab.json','config.json','config.yaml','config.yml'):
    p=d/f; out[f]=p.as_posix() if p.exists() else None
  if out.get('model.safetensors'): out['weights_sha256_head']=sha256_head(d/'model.safetensors')
  return out
R={'intent':inspect_pkl(INTENT), 'spam':inspect_pkl(SPAM), 'kie':inspect_kie(KIE)}
(OUT_JSON).write_text(json.dumps(R,ensure_ascii=False,indent=2),'utf-8')
md=['# MODEL_PROBE','']
for k,v in R.items():
  md.append(f'## {k.upper()}'); md.append(''); md.append('')
(OUT_MD).write_text('\n'.join(md),'utf-8')
print('[MANIFEST]', OUT_JSON.as_posix()); print('[MARKDOWN]', OUT_MD.as_posix())
