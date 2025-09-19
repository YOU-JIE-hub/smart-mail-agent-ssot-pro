import os,sys,hashlib,re,json,traceback,joblib,types
from pathlib import Path
import numpy as np
from sklearn.pipeline import make_pipeline
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
def is_pred_like(o): return any(hasattr(o,a) for a in('predict','predict_proba','decision_function'))
def has_text_front(p):
  # 嘗試判斷第一階是否文字向量器（盡力而為）
  name=getattr(p,'steps',None)
  try:
    if name: 
      first=p.steps[0][1]
      return isinstance(first,TfidfVectorizer) or 'vectorizer' in str(type(first)).lower()
  except Exception: pass
  return False
def find_estimator(obj, seen=None):
  seen=seen or set()
  if id(obj) in seen: return None
  seen.add(id(obj))
  if is_pred_like(obj): return obj
  if isinstance(obj,dict):
    # 常見鍵優先
    for k in ('pipeline','model','estimator','clf','classifier'): 
      if k in obj and is_pred_like(obj[k]): return obj[k]
    for v in obj.values(): 
      r=find_estimator(v,seen)
      if r is not None: return r
  if isinstance(obj,(list,tuple)):
    for v in obj:
      r=find_estimator(v,seen)
      if r is not None: return r
  return None
def to_text_pipeline(obj):
  # 1) dict：若同時有 vectorizer+clf 直接拼
  if isinstance(obj,dict):
    vec = obj.get('vectorizer') or obj.get('vect') or obj.get('tfidf') or obj.get('bow')
    clf = obj.get('clf') or obj.get('classifier') or obj.get('model') or obj.get('estimator')
    if vec is not None and clf is not None:
      try: return make_pipeline(vec, clf)
      except Exception: pass
  # 2) 找到底層 estimator，不論來源為何，一律補 Tfidf 在前
  est = find_estimator(obj)
  if est is not None:
    try: return make_pipeline(TfidfVectorizer(ngram_range=(1,2), min_df=1), est)
    except Exception: return est  # 最後退路：直接用（部分模型可吃 list[str]）
  return None
def record_shape_dump(out_dir, tag, obj):
  info={'type':str(type(obj))}
  if isinstance(obj,dict): info['top_keys']=sorted(list(obj.keys()))[:32]
  (out_dir/f'{tag}_object.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),'utf-8')
# ---- Intent ----
ip=os.environ.get('INTENT_PKL')
if ip and Path(ip).exists():
  raw=robust_load(ip); record_shape_dump(OUTI,'intent_raw',raw)
  pipe=to_text_pipeline(raw)
  X=[]; y=[]
  for s in Path('data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
    if not s.strip(): continue
    o=json.loads(s); X.append(o.get('text','')); y.append(o.get('label',''))
  try:
    rep=classification_report(y, pipe.predict(X), output_dict=True, zero_division=0)
    (OUTI/'metrics.json').write_text(json.dumps({'classification_report':rep},ensure_ascii=False,indent=2),'utf-8')
    (OUTI/'MODEL_CARD.md').write_text(f'# Model Card — intent (v{TODAY})\n- Source: forced-pipeline\n- PKL: {ip}\n- sha256_head: {sha256_head(ip)}\n','utf-8')
  except Exception as e:
    (OUTI/'metrics.json').write_text(json.dumps({'status':'error','error':str(e)[:1200]},ensure_ascii=False,indent=2),'utf-8')
else:
  (OUTI/'metrics.json').write_text(json.dumps({'status':'skipped','reason':'model_missing'},ensure_ascii=False),'utf-8')
# ---- Spam ----
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
  raw=robust_load(sp); record_shape_dump(OUTS,'spam_raw',raw)
  pipe=to_text_pipeline(raw)
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
      src='forced-pipeline'
    else:
      sc=keyword_score(X); src='baseline-rules'
    roc=None; pr=None
    try: roc=float(roc_auc_score(y,sc))
    except Exception: pass
    try: pr=float(average_precision_score(y,sc))
    except Exception: pass
    (OUTS/'metrics.json').write_text(json.dumps({'roc_auc':roc,'pr_auc':pr,'source':src},ensure_ascii=False,indent=2),'utf-8')
    (OUTS/'thresholds.json').write_text(json.dumps({'tau':0.5},ensure_ascii=False,indent=2),'utf-8')
  except Exception as e:
    (OUTS/'metrics.json').write_text(json.dumps({'status':'error','error':str(e)[:1200]},ensure_ascii=False,indent=2),'utf-8')
else:
  (OUTS/'metrics.json').write_text(json.dumps({'status':'skipped','reason':'model_missing'},ensure_ascii=False,indent=2),'utf-8')
# ---- KIE（占位） ----
L=[l for l in Path('data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
ok=sum(1 for t in L if re.search(r'(SO-|INV-|發票|訂單|amount|金額|電話|mobile|tel|No\.|#\d+|\b\d{2,4}[- ]?\d{3,4}\b)', t, re.I))
(OUTK/'metrics.json').write_text(json.dumps({'regex_parse_rate': (ok/len(L) if L else 0.0), 'n': len(L)},ensure_ascii=False,indent=2),'utf-8')
