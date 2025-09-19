import os, sys, json, types, importlib, traceback
from pathlib import Path
import joblib
from sklearn.metrics import classification_report

pkl = os.environ.get('SMA_INTENT_ML_PKL')
if not pkl or not Path(pkl).exists(): raise SystemExit(f'[FATAL] intent pkl missing: {pkl}')

# --- 相容層：同時提供 __main__.rules_feat（類/函式）與 rules_feat 模組 ---
RulesFeaturizer = None; make_features = None
try:
    v = importlib.import_module('vendor.rules_features')
    RulesFeaturizer = getattr(v, 'RulesFeaturizer', None)
    make_features   = getattr(v, 'make_features',   None)
except Exception: pass
if RulesFeaturizer is None:
    class RulesFeaturizer:
        def __init__(self,*a,**k): pass
        def fit(self,X,y=None): return self
        def transform(self,X): return [[0.0] for _ in (X or [])]
if make_features is None:
    def make_features(text): return [0.0]

main = sys.modules.get('__main__') or types.ModuleType('__main__')
sys.modules['__main__'] = main
class rules_feat(RulesFeaturizer): pass
def rules_feat_fn(*a, **k): return RulesFeaturizer(*a, **k)
setattr(main, 'rules_feat', rules_feat)
setattr(main, 'rules_feat_fn', rules_feat_fn)
mod = types.ModuleType('rules_feat')
setattr(mod, 'RulesFeaturizer', RulesFeaturizer)
setattr(mod, 'make_features',   make_features)
setattr(mod, 'rules_feat',      rules_feat)
setattr(mod, 'rules_feat_fn',   rules_feat_fn)
sys.modules['rules_feat'] = mod

# --- 載入與評測 ---
try:
    mdl = joblib.load(pkl)
except Exception as e:
    traceback.print_exc(); raise SystemExit(2)

X, y = [], []
for line in Path('data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
    if not line.strip(): continue
    o = json.loads(line)
    X.append(o.get('text',''))
    y.append(o.get('label',''))

y_pred = mdl.predict(X)
rep = classification_report(y, y_pred, output_dict=True, zero_division=0)
outdir = Path(f'models/intent/artifacts/v{os.environ.get("TODAY","")}')
outdir.mkdir(parents=True, exist_ok=True)
(outdir/'metrics.json').write_text(json.dumps({'classification_report':rep}, ensure_ascii=False, indent=2), 'utf-8')
print('[OK] intent metrics ->', (outdir/'metrics.json').as_posix())
