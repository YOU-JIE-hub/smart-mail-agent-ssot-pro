import os,sys,hashlib,re,json,traceback,joblib,inspect,types
from pathlib import Path
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, roc_auc_score, average_precision_score
TODAY=os.environ.get('TODAY') or __import__('datetime').date.today().isoformat()
root=Path.cwd()
OUTI=root/f'models/intent/artifacts/v{TODAY}'; OUTS=root/f'models/spam/artifacts/v{TODAY}'; OUTK=root/f'models/kie/artifacts/v{TODAY}'
for p in (OUTI,OUTS,OUTK): p.mkdir(parents=True, exist_ok=True)
def sha256_head(p,cap=4*1024*1024):
  h=hashlib.sha256(); r=0
  with open(p,'rb') as f:
    while True:
      b=f.read(1048576)
      if not b: break
      h.update(b); r+=len(b)
      if r>=cap: h.update(b'__TRUNCATED__'); break
  return h.hexdigest()
def robust_load(path):
  for _ in range(24):
    try: return joblib.load(path)
    except Exception as e:
      et=''.join(traceback.format_exception_only(type(e),e))
      m1=re.search(r"No module named '([^']+)'",et); m2=re.search(r"Can't get attribute '([^']+)' on <module '([^']+)'",et); m3=re.search(r"module '([^']+)' has no attribute '([^']+)'",et)
      if m1: __import__('sitecustomize'); sys.ensure_missing_class(m1.group(1),'_Shim'); continue
      if m2: __import__('sitecustomize'); sys.ensure_missing_class(m2.group(2), m2.group(1)); continue
      if m3: __import__('sitecustomize'); sys.ensure_missing_class(m3.group(1), m3.group(2)); continue
      raise
def snapshot(obj):
  info={'type':str(type(obj))}
  try: info['module']=inspect.getmodule(obj).__name__
  except: pass
  if isinstance(obj,dict): info['top_keys']=sorted(list(obj.keys()))[:64]
  for a in ('classes_','n_features_in_','feature_names_in_'):
    if hasattr(obj,a):
      try: v=getattr(obj,a); info[a]=int(v) if isinstance(v,int) else (len(v) if hasattr(v,'__len__') else str(type(v)))
      except: pass
  if isinstance(obj,Pipeline): info['pipeline_steps']=[n for n,_ in obj.steps]
  return info
def is_pred_like(o): return any(hasattr(o,a) for a in('predict','predict_proba','decision_function'))
def looks_numeric_estimator(est): return hasattr(est,'n_features_in_')
def try_build_from_dict(d):
  keys=d.keys(); vec = d.get('vectorizer') or d.get('vect') or d.get('tfidf') or d.get('bow') or d.get('preprocessor')
  clf = d.get('clf') or d.get('classifier') or d.get('model') or d.get('estimator') or d.get('final_estimator')
  if vec is not None and clf is not None:
    try: return make_pipeline(vec,clf),'dict_vec+clf'
    except Exception: pass
  # pipeline 變體
  pl = d.get('pipeline') or d.get('pipe')
  if isinstance(pl,Pipeline): return pl,'dict_pipeline'
  if isinstance(pl,(list,tuple)) and all(isinstance(t,(list,tuple)) and len(t)==2 for t in pl):
    try: return Pipeline(pl),'dict_steps_pipeline'
    except Exception: pass
  steps = d.get('steps')
  if isinstance(steps,(list,tuple)) and all(isinstance(t,(list,tuple)) and len(t)==2 for t in steps):
    try: return Pipeline(steps),'dict_steps_pipeline2'
    except Exception: pass
  return None,None
def dfs_find_estimator(x,seen):
  if x is None: return None
  if id(x) in seen: return None
  seen.add(id(x))
  if isinstance(x,Pipeline): return x
  if is_pred_like(x): return x
  if isinstance(x,dict):
    pl,_=try_build_from_dict(x)
    if pl is not None: return pl
    for v in x.values():
      r=dfs_find_estimator(v,seen);  
      if r is not None: return r
  if isinstance(x,(list,tuple)):
    # 支援 [(name, est)] 形式
    if all(isinstance(t,(list,tuple)) and len(t)==2 for t in x):
      try: return Pipeline(x)
      except Exception: pass
    for v in x:
      r=dfs_find_estimator(v,seen); 
      if r is not None: return r
  # GridSearchCV / RandomizedSearchCV
  if hasattr(x,'best_estimator_'): return getattr(x,'best_estimator_')
  return None
def build_text_pipeline(obj):
  est=dfs_find_estimator(obj,set())
  if est is None: return None,'not_found'
  if looks_numeric_estimator(est): return None,'numeric_only_estimator'
  try: return make_pipeline(TfidfVectorizer(ngram_range=(1,2),min_df=1), est), 'tfidf+estimator'
  except Exception: return est,'raw_estimator'
# ===== Intent =====
ip=os.environ.get('INTENT_PKL')
if ip and Path(ip).exists():
  raw=robust_load(ip); (OUTI/'intent_raw_object.json').write_text(json.dumps(snapshot(raw),ensure_ascii=False,indent=2),'utf-8')
  pipe,mode=build_text_pipeline(raw)
  X=[]; y=[]
  for s in Path('data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
    if not s.strip(): continue
    o=json.loads(s); X.append(o.get('text','')); y.append(o.get('label',''))
  try:
    if pipe is None: raise RuntimeError(f'cannot_build_text_pipeline: {mode}')
    pred=pipe.predict(X); rep=classification_report(y,pred,output_dict=True,zero_division=0)
    (OUTI/'metrics.json').write_text(json.dumps({'mode':mode,'classification_report':rep},ensure_ascii=False,indent=2),'utf-8')
  except Exception as e:
    (OUTI/'metrics.json').write_text(json.dumps({'status':'error','error':str(e)[:1000]},ensure_ascii=False,indent=2),'utf-8')
else:
  (OUTI/'metrics.json').write_text(json.dumps({'status':'skipped','reason':'model_missing'},ensure_ascii=False),'utf-8')
# ===== Spam =====
sp=os.environ.get('SPAM_PKL')
def keyword_score(xs):
  bad=('free','免費','中獎','高收益','點我','verify','帳號','update','限時','投資','bitcoin','.js','http://','https://')
  good=('會議','附件','採購','報價','invoice','訂單','請協助','請查收')
  import math
  sc=[]
  for t in xs:
    s=t.lower(); p=sum(w in s for w in bad) - 0.5*sum(w in s for w in good); sc.append(1/(1+math.exp(-max(-2.0,min(2.0,p)))))
  return sc
if sp and Path(sp).exists():
  raw=robust_load(sp); (OUTS/'spam_raw_object.json').write_text(json.dumps(snapshot(raw),ensure_ascii=False,indent=2),'utf-8')
  pipe,mode=build_text_pipeline(raw)
  X=[]; y=[]
  for s in Path('data/spam_eval/dataset.jsonl').read_text('utf-8').splitlines():
    if not s.strip(): continue
    o=json.loads(s); X.append(o.get('text','')); y.append(int(o.get('label',0)))
  try:
    if pipe is not None:
      if hasattr(pipe,'predict_proba'): sc=[float(p[1]) for p in pipe.predict_proba(X)]
      elif hasattr(pipe,'decision_function'):
        df=pipe.decision_function(X); sc=[float(t) for t in (df.tolist() if hasattr(df,'tolist') else df)]
      else: sc=[float(t) for t in pipe.predict(X)]
      src=f'pipeline:{mode}'
    else:
      sc=keyword_score(X); src=f'baseline:{mode}'
    roc=None; pr=None
    try: roc=float(roc_auc_score(y,sc))
    except Exception: pass
    try: pr=float(average_precision_score(y,sc))
    except Exception: pass
    (OUTS/'metrics.json').write_text(json.dumps({'source':src,'roc_auc':roc,'pr_auc':pr},ensure_ascii=False,indent=2),'utf-8')
    (OUTS/'thresholds.json').write_text(json.dumps({'tau':0.5},ensure_ascii=False,indent=2),'utf-8')
  except Exception as e:
    (OUTS/'metrics.json').write_text(json.dumps({'status':'error','error':str(e)[:1000]},ensure_ascii=False,indent=2),'utf-8')
else:
  (OUTS/'metrics.json').write_text(json.dumps({'status':'skipped','reason':'model_missing'},ensure_ascii=False,indent=2),'utf-8')
# ===== KIE 占位 =====
L=[l for l in Path('data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
ok=sum(1 for t in L if re.search(r'(SO-|INV-|發票|訂單|amount|金額|電話|mobile|tel|No\.|#\d+|\b\d{2,4}[- ]?\d{3,4}\b)', t, re.I))
(OUTK/'metrics.json').write_text(json.dumps({'regex_parse_rate': (ok/len(L) if L else 0.0), 'n': len(L)},ensure_ascii=False,indent=2),'utf-8')
