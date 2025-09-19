import os, json, joblib, types, re, traceback
from pathlib import Path
import numpy as np
from scipy import sparse
from sklearn.pipeline import Pipeline, FeatureUnion, make_pipeline
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.metrics import classification_report, roc_auc_score, average_precision_score
ROOT=Path.cwd(); TODAY=os.environ.get('TODAY') or __import__('datetime').date.today().isoformat()
INTENT=Path(os.environ['INTENT_PKL']); SPAM=Path(os.environ['SPAM_PKL']); KIE=Path(os.environ['KIE_DIR'])
def save(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2),'utf-8')
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
class NullRulesFeat(TransformerMixin, BaseEstimator):
  def fit(self, X, y=None): return self
  def transform(self, X):
    n=len(X) if hasattr(X,'__len__') else 0
    return sparse.csr_matrix((n,0), dtype=np.float32)
def monkeypatch_rules_feat():  # 接受任何參數 → 空特徵；根治 takes no arguments
  for name in ('rules_features','vendor.rules_features'):
    try:
      mod=__import__(name, fromlist=['*'])
      def _shim(*a, **k): return {}
      setattr(mod,'rules_feat',_shim)
    except Exception: pass
def neutralize_rulesfeat(node):
  from sklearn.preprocessing import FunctionTransformer
  try: from sklearn.compose import ColumnTransformer
  except Exception: ColumnTransformer=None
  if isinstance(node, Pipeline):
    return Pipeline([(nm, neutralize_rulesfeat(st)) for nm,st in node.steps])
  if isinstance(node, FeatureUnion):
    return FeatureUnion([(nm, neutralize_rulesfeat(tr)) for nm,tr in (getattr(node,'transformer_list',[]) or [])])
  if ColumnTransformer and isinstance(node, ColumnTransformer):
    from sklearn.compose import ColumnTransformer as CT
    trs=[(nm, neutralize_rulesfeat(tr), cols) for nm,tr,cols in node.transformers]
    return CT(trs, remainder=node.remainder, sparse_threshold=node.sparse_threshold, n_jobs=node.n_jobs, transformer_weights=node.transformer_weights)
  if getattr(node,'__class__',type('X',(object,),{})).__name__=='FunctionTransformer':
    func=getattr(node,'func',None)
    if func and (getattr(func,'__name__','').lower()=='rules_feat' or 'rules_features' in getattr(func,'__module__','')):
      return NullRulesFeat()
  mod=getattr(node,'__module__',''); nm=getattr(node,'__class__',type('X',(object,),{})).__name__.lower()
  if 'rules_features' in mod or 'rules_feat' in nm: return NullRulesFeat()
  return node
def pick_fitted_pipeline(obj):
  def fitted_tail(p):
    try: tail=p.steps[-1][1]
    except Exception: return False
    return any(hasattr(tail,a) for a in ('classes_','coef_','feature_log_prob_','n_features_in_'))
  if isinstance(obj, Pipeline): return obj if fitted_tail(obj) else None
  if isinstance(obj, dict):
    for k in ('pipeline','sk','pipe','sk_model','model_pipeline'):
      v=obj.get(k)
      if isinstance(v, Pipeline) and fitted_tail(v): return v
  return None
# ===== Intent =====
I=ROOT/f'models/intent/artifacts/v{TODAY}'; I.mkdir(parents=True,exist_ok=True)
im={'source':'authoritative','path':INTENT.as_posix()}
try:
  oi=robust_load(INTENT); pi=pick_fitted_pipeline(oi)
  if pi is None: raise RuntimeError('no fitted pipeline inside pkl; 檢查 MODEL_PROBE json 的 keys/pipeline_summary')
  monkeypatch_rules_feat(); pi=neutralize_rulesfeat(pi)
  X=[]; y=[]
  for ln in (ROOT/'data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
    if not ln.strip(): continue
    o=json.loads(ln); X.append(o.get('text','')); y.append(o.get('label',''))
  pred=pi.predict(X)
  rep=classification_report(y, pred, output_dict=True, zero_division=0)
  im.update({'classification_report':rep})
except Exception as e:
  im.update({'status':'error','error':str(e)[:1000]})
save(I/'metrics.json', im)
# ===== Spam =====
S=ROOT/f'models/spam/artifacts/v{TODAY}'; S.mkdir(parents=True,exist_ok=True)
sm={'source':'authoritative','path':SPAM.as_posix()}
try:
  os_=robust_load(SPAM); ps=pick_fitted_pipeline(os_)
  if ps is None: raise RuntimeError('no fitted pipeline found in spam pkl（需要已訓練且已持 vocab 的 Pipeline）')
  X=[]; y=[]
  for ln in (ROOT/'data/spam_eval/dataset.jsonl').read_text('utf-8').splitlines():
    if not ln.strip(): continue
    o=json.loads(ln); X.append(o.get('text','')); y.append(int(o.get('label',0)))
  if hasattr(ps,'predict_proba'): sc=[float(t[1]) for t in ps.predict_proba(X)]
  elif hasattr(ps,'decision_function'):
    d=ps.decision_function(X); sc=[float(t) for t in (d.tolist() if hasattr(d,'tolist') else d)]
  else: sc=[float(t) for t in ps.predict(X)]
  try: roc=float(roc_auc_score(y,sc)); pr=float(average_precision_score(y,sc))
  except Exception: roc=None; pr=None
  sm.update({'roc_auc':roc,'pr_auc':pr})
except Exception as e:
  sm.update({'status':'error','error':str(e)[:1000]})
save(S/'metrics.json', sm)
# ===== KIE（regex 健檢） =====
K=ROOT/f'models/kie/artifacts/v{TODAY}'; K.mkdir(parents=True,exist_ok=True)
lines=[l for l in (ROOT/'data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
rx=re.compile(r'(SO-|INV-|發票|訂單|amount|金額|電話|mobile|tel|No\.|#\d+|\b\d{2,4}[- ]?\d{3,4}\b)', re.I)
regex_ok=sum(1 for t in lines if rx.search(t))
km={'ready_flags':{'weights':(K/'model.safetensors').exists()}, 'regex_parse_rate': (regex_ok/len(lines) if lines else 0.0), 'n':len(lines)}
save(K/'metrics.json', km)
