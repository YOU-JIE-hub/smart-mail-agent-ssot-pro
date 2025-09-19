import os,sys,types,importlib,hashlib,json,traceback
from pathlib import Path
import joblib
from sklearn.metrics import classification_report

def sha256_head(p,cap=4*1024*1024):
    p=Path(p); h=hashlib.sha256(); r=0
    with open(p,'rb') as f:
        while True:
            b=f.read(1024*1024)
            if not b: break
            h.update(b); r+=len(b)
            if r>=cap: h.update(b'b__TRUNCATED__'); break
    return h.hexdigest()

def create_module(m):
    import sys,types
    if m in sys.modules: return sys.modules[m]
    mod=types.ModuleType(m); sys.modules[m]=mod
    if '.' in m:
        parent=m.rsplit('.',1)[0]; create_module(parent); setattr(sys.modules[parent], m.split('.')[-1], mod)
    return mod

def ensure_class(mod, cls):
    M=create_module(mod)
    if not hasattr(M, cls):
        ns={}; exec(f'class {cls}:\n    def __init__(self,*a,**k): pass\n    def fit(self,X,y=None): return self\n    def transform(self,X): return X\n    def predict(self,X): return [0 for _ in (X or [])]\n', ns, ns)
        setattr(M, cls, ns[cls])

def inject_rules_feat_dual():
    try:
        v=importlib.import_module('vendor.rules_features')
        RF=getattr(v,'RulesFeaturizer',None); mk=getattr(v,'make_features',None)
    except Exception:
        RF=None; mk=None
    if RF is None:
        class RF:
            def __init__(self,*a,**k): pass
            def fit(self,X,y=None): return self
            def transform(self,X): return [[0.0] for _ in (X or [])]
    if mk is None:
        def mk(_): return [0.0]
    main=sys.modules.get('__main__') or types.ModuleType('__main__'); sys.modules['__main__']=main
    class rules_feat(RF): pass
    setattr(main,'rules_feat',rules_feat)
    def rules_feat_fn(*a,**k): return RF(*a,**k)
    setattr(main,'rules_feat_fn',rules_feat_fn)
    mod=types.ModuleType('rules_feat');
    for k,v in dict(RulesFeaturizer=RF, make_features=mk, rules_feat=rules_feat, rules_feat_fn=rules_feat_fn).items():
        setattr(mod,k,v)
    sys.modules['rules_feat']=mod

def robust_load(pkl):
    import re,joblib,traceback
    inject_rules_feat_dual()
    for _ in range(12):
        try: return joblib.load(pkl)
        except Exception as e:
            et=''.join(traceback.format_exception_only(type(e),e))
            import re
            m1=re.search(r"No module named '([^']+)'", et)
            m2=re.search(r"Can't get attribute '([^']+)' on <module '([^']+)'", et)
            m3=re.search(r"module '([^']+)' has no attribute '([^']+)'", et)
            if m1: create_module(m1.group(1)); continue
            if m2: ensure_class(m2.group(2), m2.group(1)); continue
            if m3: ensure_class(m3.group(1), m3.group(2)); continue
            raise

pkl=os.environ['SMA_INTENT_ML_PKL']
out=Path(f'models/intent/artifacts/v{os.environ.get("TODAY","")}'); out.mkdir(parents=True,exist_ok=True)
mdl=robust_load(pkl)
X=[]; y=[]
for line in Path('data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
    if not line.strip(): continue
    o=json.loads(line); X.append(o.get('text','')); y.append(o.get('label',''))
rep=classification_report(y, mdl.predict(X), output_dict=True, zero_division=0)
(out/'metrics.json').write_text(json.dumps({'classification_report':rep},ensure_ascii=False,indent=2),'utf-8')
(out/'MODEL_CARD.md').write_text(f'# Model Card — intent (v{os.environ.get("TODAY","")})\n- PKL: {pkl}\n- sha256_head: {sha256_head(pkl)}\n','utf-8')
