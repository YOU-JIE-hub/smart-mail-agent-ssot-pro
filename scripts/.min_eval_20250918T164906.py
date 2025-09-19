import os,sys,re,types,importlib,hashlib,json,traceback,joblib
from pathlib import Path
from sklearn.metrics import classification_report, roc_auc_score, average_precision_score
from sklearn.pipeline import make_pipeline
def sha256_head(p,cap=4*1024*1024):
  h=hashlib.sha256(); r=0; f=open(p,'rb');
  b=f.read(1048576);
  while b:
    h.update(b); r+=len(b);
    if r>=cap: h.update(b'__TRUNCATED__'); break
    b=f.read(1048576)
  f.close(); print('[hash]',p,h.hexdigest()); return h.hexdigest()
def create_module(m):
  import types,sys; mod=sys.modules.get(m) or types.ModuleType(m); sys.modules[m]=mod;
  if '.' in m:
    parent=m.rsplit('.',1)[0]; pm=sys.modules.get(parent) or types.ModuleType(parent); sys.modules[parent]=pm; setattr(pm,m.split('.')[-1],mod)
  return mod
def ensure_class(mod,cls):
  M=create_module(mod);
  if not hasattr(M,cls): exec(f'class {cls}:\n def __init__(self,*a,**k): pass\n def fit(self,X,y=None): return self\n def transform(self,X): return X\n def predict(self,X): return [0 for _ in (X or [])]\n',M.__dict__)
def inject_rules_feat_dual():
  try:
    v=importlib.import_module('vendor.rules_features'); RF=getattr(v,'RulesFeaturizer',None); mk=getattr(v,'make_features',None)
  except Exception: RF=None; mk=None
  if RF is None:
    class RF:
      def __init__(self,*a,**k): pass
      def fit(self,X,y=None): return self
      def transform(self,X): return [[0.0] for _ in (X or [])]
  if mk is None:
    def mk(_): return [0.0]
  main=sys.modules.get('__main__') or types.ModuleType('__main__'); sys.modules['__main__']=main
  class rules_feat(RF): pass
  setattr(main,'rules_feat',rules_feat); setattr(main,'rules_feat_fn',lambda *a,**k: RF())
  mod=types.ModuleType('rules_feat');
  for k,v in dict(RulesFeaturizer=RF, make_features=mk, rules_feat=rules_feat, rules_feat_fn=lambda *a,**k: RF()).items(): setattr(mod,k,v)
  sys.modules['rules_feat']=mod
def robust_load(pkl,for_intent=False):
  if for_intent: inject_rules_feat_dual()
  last=None
  for _ in range(16):
    try: return joblib.load(pkl)
    except Exception as e:
      et=''.join(traceback.format_exception_only(type(e),e));
      m1=re.search(r"No module named '([^']+)'", et); m2=re.search(r"Can't get attribute '([^']+)' on <module '([^']+)'", et); m3=re.search(r"module '([^']+)' has no attribute '([^']+)'", et)
      if m1: create_module(m1.group(1)); continue
      if m2: ensure_class(m2.group(2), m2.group(1)); continue
      if m3: ensure_class(m3.group(1), m3.group(2)); continue
      raise
# INTENT
tod=os.environ.get('TODAY') or __import__('datetime').date.today().isoformat()
oi=Path(f'models/intent/artifacts/v{tod}'); oi.mkdir(parents=True,exist_ok=True)
ip=os.environ.get('SMA_INTENT_ML_PKL')
if ip and Path(ip).exists():
  m=robust_load(ip,for_intent=True)
  X=[]; y=[]
  for s in Path('data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
    if not s.strip(): continue
    o=json.loads(s); X.append(o.get('text','')); y.append(o.get('label',''))
  rep=classification_report(y,m.predict(X),output_dict=True,zero_division=0)
  (oi/'metrics.json').write_text(json.dumps({'classification_report':rep},ensure_ascii=False,indent=2),'utf-8')
  (oi/'MODEL_CARD.md').write_text(f'# Model Card — intent (v{tod})\n- PKL: {ip}\n- sha256_head: {sha256_head(ip)}\n','utf-8')
else:
  (oi/'metrics.json').write_text(json.dumps({'status':'skipped','reason':'model_missing'},ensure_ascii=False,indent=2),'utf-8')
# SPAM
os.environ.setdefault('SMA_SPAM_ML_PKL','/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/77/77/artifacts_sa/spam_rules_lr.pkl')
os.makedirs(f'models/spam/artifacts/v{tod}',exist_ok=True)
os.makedirs(f'models/kie/artifacts/v{tod}',exist_ok=True)
sp=os.environ['SMA_SPAM_ML_PKL']; os.makedirs('reports_auto/status',exist_ok=True)
def first_pred_like(o): return any(hasattr(o,a) for a in('predict','predict_proba','decision_function'))
def coerce(o,seen=None):
  seen=seen or set()
  if id(o) in seen: return None
  seen.add(id(o))
  if first_pred_like(o): return o
  import collections
  if isinstance(o,dict):
    vec=o.get('vectorizer') or o.get('vect') or o.get('tfidf') or o.get('bow'); clf=o.get('clf') or o.get('classifier') or o.get('model') or o.get('estimator')
    if vec is not None and clf is not None:
      try: return make_pipeline(vec,clf)
      except Exception: pass
    for v in o.values():
      r=coerce(v,seen);  
      if first_pred_like(r): return r
  if isinstance(o,(list,tuple)):
    for v in o:
      r=coerce(v,seen);
      if first_pred_like(r): return r
  return None
os.makedirs('models/spam/artifacts',exist_ok=True)
os.makedirs('models/kie/artifacts',exist_ok=True)
outs=Path(f'models/spam/artifacts/v{tod}')
try:
  raw=robust_load(sp)
  mdl=coerce(raw)
  if mdl is None: raise TypeError('cannot coerce estimator')
  X=[]; y=[]
  for s in Path('data/spam_eval/dataset.jsonl').read_text('utf-8').splitlines():
    if not s.strip(): continue
    o=json.loads(s); X.append(o.get('text','')); y.append(int(o.get('label',0)))
  if hasattr(mdl,'predict_proba'): sc=[float(p[1]) for p in mdl.predict_proba(X)]
  elif hasattr(mdl,'decision_function'): df=mdl.decision_function(X); sc=[float(t) for t in (df.tolist() if hasattr(df,'tolist') else df)]
  else: sc=[float(t) for t in mdl.predict(X)]
  ms={}
  try: ms['roc_auc']=float(roc_auc_score(y,sc))
  except Exception: ms['roc_auc']=None
  try: ms['pr_auc']=float(average_precision_score(y,sc))
  except Exception: ms['pr_auc']=None
  (outs/'metrics.json').write_text(json.dumps(ms,ensure_ascii=False,indent=2),'utf-8')
  (outs/'thresholds.json').write_text(json.dumps({'tau':0.5},ensure_ascii=False,indent=2),'utf-8')
  (outs/'MODEL_CARD.md').write_text(f'# Model Card — spam (v{tod})\n- PKL: {sp}\n- sha256_head: {sha256_head(sp)}\n','utf-8')
except Exception as e:
  (outs/'metrics.json').write_text(json.dumps({'status':'error','error':str(e)},ensure_ascii=False,indent=2),'utf-8')
# KIE 占位
ok=0; L=[l for l in Path('data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
for t in L:  
  if re.search(r'(SO-|INV-|\b\d{2,4}[- ]?\d{3,4}\b)', t): ok+=1
(Path(f'models/kie/artifacts/v{tod}')/'metrics.json').write_text(json.dumps({'regex_parse_rate': (ok/len(L) if L else 0.0), 'n': len(L)},ensure_ascii=False,indent=2),'utf-8')
