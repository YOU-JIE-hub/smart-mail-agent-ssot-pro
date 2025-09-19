import os, json, joblib, traceback, types, re, hashlib
from pathlib import Path
import numpy as np
from sklearn.pipeline import Pipeline, FeatureUnion, make_pipeline
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, roc_auc_score, average_precision_score
from scipy import sparse
ROOT=Path.cwd(); TODAY=os.environ.get('TODAY') or __import__('datetime').date.today().isoformat()
INTENT_PKL=Path(os.environ['INTENT_PKL']); SPAM_PKL=Path(os.environ['SPAM_PKL']); KIE_DIR=Path(os.environ['KIE_DIR'])
def save_json(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2),'utf-8')
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
  # 產出 0 欄位（讓 FeatureUnion/ColumnTransformer 接上時不影響維度；避免簽名錯誤）
  def fit(self, X, y=None): return self
  def transform(self, X):
    n=len(X) if hasattr(X,'__len__') else 0
    return sparse.csr_matrix((n,0), dtype=np.float32)
def neutralize_rulesfeat_in_pipeline(pl):
  # 遞迴地把任何名為 'rules_feat' 或來源自 rules_features.rules_feat 的變換器替換成 NullRulesFeat()
  if isinstance(pl, Pipeline):
    steps=[]
    for name, step in pl.steps:
      steps.append((name, neutralize_rulesfeat_in_pipeline(step)))
    return Pipeline(steps)
  # FeatureUnion / ColumnTransformer
  try:
    from sklearn.compose import ColumnTransformer
  except Exception:
    ColumnTransformer = None
  if isinstance(pl, FeatureUnion):
    trs=[]
    for name, trans, *rest in getattr(pl, 'transformer_list', []) or []:
      t = neutralize_rulesfeat_in_pipeline(trans)
      trs.append((name, t))
    nu = FeatureUnion(trs)
    return nu
  if ColumnTransformer is not None and isinstance(pl, ColumnTransformer):
    trs=[]
    for name, trans, cols in pl.transformers:
      t = neutralize_rulesfeat_in_pipeline(trans)
      trs.append((name, t, cols))
    from sklearn.compose import ColumnTransformer as CT
    return CT(trs, remainder=pl.remainder, sparse_threshold=pl.sparse_threshold, n_jobs=pl.n_jobs, transformer_weights=pl.transformer_weights)
  # 單一變換器：若來自 rules_features 或 名稱含 rules_feat，換成 NullRulesFeat
  mod = getattr(pl, '__module__', '')
  name = getattr(pl, '__class__', type('X',(object,),{})).__name__
  if 'rules_features' in mod or 'RulesFeat' in name or 'rules_feat' in name.lower():
    return NullRulesFeat()
  # 保留原物件
  return pl
def to_text_pipeline_from_object(obj):
  # 1) 直接 Pipeline
  if isinstance(obj, Pipeline): return obj
  # 2) 字典優先順序：pipeline -> sk -> model -> clf -> estimator
  if isinstance(obj, dict):
    for k in ('pipeline','sk','pipe','sk_model','model','clf','estimator'):
      if k in obj:
        cand=obj[k]
        if isinstance(cand, Pipeline): return cand
        # 估計器：包 TF-IDF
        if hasattr(cand, 'fit') and (hasattr(cand,'predict') or hasattr(cand,'predict_proba') or hasattr(cand,'decision_function')):
          return make_pipeline(TfidfVectorizer(ngram_range=(1,2),min_df=1), cand)
  # 3) 其他估計器：包 TF-IDF
  if hasattr(obj, 'fit'):
    return make_pipeline(TfidfVectorizer(ngram_range=(1,2),min_df=1), obj)
  # 4) 都不是：回 None
  return None
# ===== Intent =====
I=ROOT/f'models/intent/artifacts/v{TODAY}'; I.mkdir(parents=True,exist_ok=True)
im={'source':'authoritative','path':INTENT_PKL.as_posix()}
try:
  oi=robust_load(INTENT_PKL)
  pi=to_text_pipeline_from_object(oi)
  if pi is None: raise RuntimeError('intent: no usable pipeline/estimator')
  pi = neutralize_rulesfeat_in_pipeline(pi)
  X=[]; y=[]
  for ln in (ROOT/'data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
    if not ln.strip(): continue
    o=json.loads(ln); X.append(o.get('text','')); y.append(o.get('label',''))
  pred=pi.predict(X)
  rep=classification_report(y, pred, output_dict=True, zero_division=0)
  im.update({'classification_report':rep})
except Exception as e:
  im.update({'status':'error','error':str(e)[:1200]})
save_json(I/'metrics.json', im)
# ===== Spam =====
S=ROOT/f'models/spam/artifacts/v{TODAY}'; S.mkdir(parents=True,exist_ok=True)
sm={'source':'authoritative','path':SPAM_PKL.as_posix()}
try:
  os_=robust_load(SPAM_PKL)
  ps=to_text_pipeline_from_object(os_)
  if ps is None: raise RuntimeError('spam: no usable pipeline/estimator')
  # 不需要中和 rules_feat（通常 spam 無此步），若有也一併中和
  ps = neutralize_rulesfeat_in_pipeline(ps)
  X=[]; y=[]
  for ln in (ROOT/'data/spam_eval/dataset.jsonl').read_text('utf-8').splitlines():
    if not ln.strip(): continue
    o=json.loads(ln); X.append(o.get('text','')); y.append(int(o.get('label',0)))
  if hasattr(ps,'predict_proba'): sc=[float(p[1]) for p in ps.predict_proba(X)]
  elif hasattr(ps,'decision_function'):
    df=ps.decision_function(X); sc=[float(t) for t in (df.tolist() if hasattr(df,'tolist') else df)]
  else: sc=[float(t) for t in ps.predict(X)]
  try: roc=float(roc_auc_score(y,sc)); pr=float(average_precision_score(y,sc))
  except Exception: roc=None; pr=None
  sm.update({'roc_auc':roc,'pr_auc':pr})
except Exception as e:
  sm.update({'status':'error','error':str(e)[:1200]})
save_json(S/'metrics.json', sm)
# ===== KIE（維持先前 header/regex 健檢） =====
K=ROOT/f'models/kie/artifacts/v{TODAY}'; K.mkdir(parents=True,exist_ok=True)
kw=KIE_DIR/'model.safetensors'; okW=kw.exists()
tok=[x for x in ['tokenizer.json','sentencepiece.bpe.model','vocab.json'] if (KIE_DIR/x).exists()]
cfg=[x for x in ['config.json','config.yaml','config.yml'] if (KIE_DIR/x).exists()]
lines=[l for l in (ROOT/'data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
import re
regex_ok=sum(1 for t in lines if re.search(r'(SO-|INV-|發票|訂單|amount|金額|電話|mobile|tel|No\.|#\d+|\b\d{2,4}[- ]?\d{3,4}\b)', t, re.I))
km={'ready_flags':{'weights':okW,'tokenizer':bool(tok),'config':bool(cfg)}, 'regex_parse_rate': (regex_ok/len(lines) if lines else 0.0), 'n':len(lines)}
save_json(K/'metrics.json', km)
