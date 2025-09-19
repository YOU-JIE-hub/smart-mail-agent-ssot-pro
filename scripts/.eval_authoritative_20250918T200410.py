import os, json, joblib, traceback, types, re, hashlib
from pathlib import Path
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, roc_auc_score, average_precision_score
ROOT=Path.cwd(); TODAY=os.environ.get('TODAY') or __import__('datetime').date.today().isoformat()
INTENT_PKL=Path(os.environ['INTENT_PKL']); SPAM_PKL=Path(os.environ['SPAM_PKL']); KIE_DIR=Path(os.environ['KIE_DIR'])
def sha256_head(p,cap=4*1024*1024):
  h=hashlib.sha256(); r=0
  with open(p,'rb') as f:
    while True:
      b=f.read(1048576); 
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
def to_text_pipeline(obj):
  # 1) 直接是 Pipeline
  if isinstance(obj, Pipeline): return obj
  # 2) 字典含 pipeline -> 取出
  if isinstance(obj, dict) and 'pipeline' in obj and isinstance(obj['pipeline'], Pipeline): return obj['pipeline']
  # 3) 字典含 model -> 包一層 TF-IDF（處理 1D/2D）
  if isinstance(obj, dict) and 'model' in obj: return make_pipeline(TfidfVectorizer(ngram_range=(1,2), min_df=1), obj['model'])
  # 4) 其他估計器 -> 也包 TF-IDF
  return make_pipeline(TfidfVectorizer(ngram_range=(1,2), min_df=1), obj)
def save_json(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2),'utf-8')
# ===== Intent =====
I=ROOT/f'models/intent/artifacts/v{TODAY}'; I.mkdir(parents=True,exist_ok=True)
im={'source':'authoritative','path':INTENT_PKL.as_posix()}
try:
  oi=robust_load(INTENT_PKL); pi=to_text_pipeline(oi)
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
  os_=robust_load(SPAM_PKL); ps=to_text_pipeline(os_)
  X=[]; y=[]
  for ln in (ROOT/'data/spam_eval/dataset.jsonl').read_text('utf-8').splitlines():
    if not ln.strip(): continue
    o=json.loads(ln); X.append(o.get('text','')); y.append(int(o.get('label',0)))
  if hasattr(ps,'predict_proba'): sc=[float(p[1]) for p in ps.predict_proba(X)]
  elif hasattr(ps,'decision_function'):
    df=ps.decision_function(X); sc=[float(t) for t in (df.tolist() if hasattr(df,'tolist') else df)]
  else: sc=[float(t) for t in ps.predict(X)]
  try: roc=float(roc_auc_score(y,sc)); pr=float(average_precision_score(y,sc))
  except Exception as e: roc=None; pr=None
  sm.update({'roc_auc':roc,'pr_auc':pr})
except Exception as e:
  sm.update({'status':'error','error':str(e)[:1200]})
save_json(S/'metrics.json', sm)
# ===== KIE（header/regex 健檢；若你要真前向再加 torch） =====
K=ROOT/f'models/kie/artifacts/v{TODAY}'; K.mkdir(parents=True,exist_ok=True)
kw=KIE_DIR/'model.safetensors'; okW=kw.exists()
tok=[x for x in ['tokenizer.json','sentencepiece.bpe.model','vocab.json'] if (KIE_DIR/x).exists()]
cfg=[x for x in ['config.json','config.yaml','config.yml'] if (KIE_DIR/x).exists()]
lines=[l for l in (ROOT/'data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
import re
regex_ok=sum(1 for t in lines if re.search(r'(SO-|INV-|發票|訂單|amount|金額|電話|mobile|tel|No\.|#\d+|\b\d{2,4}[- ]?\d{3,4}\b)', t, re.I))
km={'ready_flags':{'weights':okW,'tokenizer':bool(tok),'config':bool(cfg)}, 'regex_parse_rate': (regex_ok/len(lines) if lines else 0.0), 'n':len(lines)}
save_json(K/'metrics.json', km)
