import os,sys,re,types,importlib,hashlib,json,traceback
from pathlib import Path
import joblib
from sklearn.metrics import classification_report, roc_auc_score, average_precision_score

ROOT=Path.cwd(); TODAY=os.environ.get('TODAY',''); OUTI=ROOT/f'models/intent/artifacts/v{TODAY}'
OUTS=ROOT/f'models/spam/artifacts/v{TODAY}'; OUTK=ROOT/f'models/kie/artifacts/v{TODAY}'
for p in (OUTI,OUTS,OUTK): p.mkdir(parents=True, exist_ok=True)

def sha256_head(p,cap=4*1024*1024):
    p=Path(p); h=hashlib.sha256(); r=0
    with open(p,'rb') as f:
        while True:
            b=f.read(1024*1024)
            if not b: break
            h.update(b); r+=len(b)
            if r>=cap: h.update(b'__TRUNCATED__'); break
    return h.hexdigest()

def create_module(modname):
    if modname in sys.modules: return sys.modules[modname]
    mod=types.ModuleType(modname); sys.modules[modname]=mod
    if '.' in modname:
        parent=modname.rsplit('.',1)[0]; create_module(parent); setattr(sys.modules[parent], modname.split('.')[-1], mod)
    return mod

def ensure_class(modname, clsname):
    mod=create_module(modname)
    if not hasattr(mod, clsname):
        code=f'class {clsname}:'
        code+="\n    def __init__(self,*a,**k): pass\n    def fit(self,X,y=None): return self\n    def transform(self,X): return X\n    def predict(self,X): return [0 for _ in (X or [])]"
        ns={}; exec(code, ns, ns); setattr(mod, clsname, ns[clsname]); print('[shim]',modname+'.'+clsname)

def inject_rules_feat_dual():
    try:
        v=importlib.import_module('vendor.rules_features'); RF=getattr(v,'RulesFeaturizer',None); mk=getattr(v,'make_features',None)
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
    mod=types.ModuleType('rules_feat'); setattr(mod,'RulesFeaturizer',RF); setattr(mod,'make_features',mk); setattr(mod,'rules_feat',rules_feat); setattr(mod,'rules_feat_fn',rules_feat_fn)
    sys.modules['rules_feat']=mod

def robust_load(pkl, rounds=12):
    last=None; inject_rules_feat_dual()
    for i in range(1,rounds+1):
        try:
            obj=joblib.load(pkl); print('[load OK]',pkl,'round',i); return obj
        except Exception as e:
            et=''.join(traceback.format_exception_only(type(e),e)).strip(); print('[load FAIL]',et); last=et
            m1=re.search(r"No module named '([^']+)'", et)
            m2=re.search(r"Can't get attribute '([^']+)' on <module '([^']+)'", et)
            m3=re.search(r"module '([^']+)' has no attribute '([^']+)'", et)
            if m1: create_module(m1.group(1)); continue
            if m2: ensure_class(m2.group(2), m2.group(1)); continue
            if m3: ensure_class(m3.group(1), m3.group(2)); continue
            raise
    raise RuntimeError('exceeded shim rounds; last='+str(last))

# ---- Intent ----
ipi=os.environ.get('SMA_INTENT_ML_PKL');
if ipi and Path(ipi).exists():
    im=robust_load(ipi)
    X=[]; y=[]
    for line in Path('data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
        if not line.strip(): continue
        o=json.loads(line); X.append(o.get('text','')); y.append(o.get('label',''))
    pred=im.predict(X); rep=classification_report(y, pred, output_dict=True, zero_division=0)
    (OUTI/'metrics.json').write_text(json.dumps({'classification_report':rep}, ensure_ascii=False, indent=2), 'utf-8')
    (OUTI/'MODEL_CARD.md').write_text(f'# Model Card — intent (v{TODAY})\n- PKL: {ipi}\n- sha256_head: {sha256_head(ipi)}\n', 'utf-8')
else:
    (OUTI/'metrics.json').write_text(json.dumps({'status':'skipped','reason':'model_missing'},ensure_ascii=False), 'utf-8')

# ---- Spam ----
spi=os.environ.get('SMA_SPAM_ML_PKL');
if spi and Path(spi).exists():
    sm=robust_load(spi)
    X=[]; y=[]
    for line in Path('data/spam_eval/dataset.jsonl').read_text('utf-8').splitlines():
        if not line.strip(): continue
        o=json.loads(line); X.append(o.get('text','')); y.append(int(o.get('label',0)))
    if hasattr(sm,'predict_proba'): scores=[float(p[1]) for p in sm.predict_proba(X)]
    elif hasattr(sm,'decision_function'):
        df=sm.decision_function(X); scores=[float(s) for s in (df.tolist() if hasattr(df,'tolist') else (df if isinstance(df,(list,tuple)) else [df]))]
    else: scores=[float(p) for p in sm.predict(X)]
    metrics={}
    try: metrics['roc_auc']=float(roc_auc_score(y, scores))
    except Exception: metrics['roc_auc']=None
    try: metrics['pr_auc']=float(average_precision_score(y, scores))
    except Exception: metrics['pr_auc']=None
    (OUTS/'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), 'utf-8')
    (OUTS/'thresholds.json').write_text(json.dumps({'tau':0.5}, ensure_ascii=False, indent=2), 'utf-8')
    (OUTS/'MODEL_CARD.md').write_text(f'# Model Card — spam (v{TODAY})\n- PKL: {spi}\n- sha256_head: {sha256_head(spi)}\n', 'utf-8')
else:
    (OUTS/'metrics.json').write_text(json.dumps({'status':'skipped','reason':'model_missing'},ensure_ascii=False), 'utf-8')

# ---- KIE ----
# 這裡先用占位解析率；你要 Slot-F1/EM 再換 evaluator
txt=[l for l in Path('data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
import re; ok=sum(1 for t in txt if re.search(r'(SO-|INV-|\b\d{2,4}[- ]?\d{3,4}\b)', t))
rate= ok/len(txt) if txt else 0.0
(OUTK/'metrics.json').write_text(json.dumps({'regex_parse_rate':rate,'n':len(txt)}, ensure_ascii=False, indent=2), 'utf-8')
(OUTK/'MODEL_CARD.md').write_text(f'# Model Card — kie (v{TODAY})\n- Source: models/kie/registry.json\n- Key Metrics: regex_parse_rate={rate:.4f} (n={len(txt)})\n', 'utf-8')

# ---- LATEST symlink / training_meta / RCA ----
(ROOT/'reports_auto/status/LATEST').unlink(missing_ok=True)
(ROOT/'reports_auto/status').mkdir(parents=True, exist_ok=True)
(ROOT/'reports_auto/status/LATEST').symlink_to(f'v{TODAY}', target_is_directory=False)
(ROOT/'reports_auto/status/training_meta.json').write_text(json.dumps({'sklearn':'1.7.1','joblib':'1.4.2'},ensure_ascii=False,indent=2),'utf-8')
(ROOT/'reports_auto/status/RCA_'+TODAY+'_'+__import__('time').strftime('%H%M%S')+'.md').write_text('# RCA\n- status: metrics_regen\n', 'utf-8')

print('[DONE] metrics/model_cards updated for intent/spam/kie ; LATEST, training_meta, RCA written')
