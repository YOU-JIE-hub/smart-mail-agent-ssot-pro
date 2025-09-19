import os, json, joblib, re
from pathlib import Path
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report
import numpy as np
from scipy import sparse

# === 關鍵修補：提供 __main__.rules_feat，與舊序列化對齊（零寬度特徵，安全中和） ===
def rules_feat(*args, **kwargs):
    X = args[0] if args else kwargs.get('X', None)
    n = len(X) if X is not None and hasattr(X,'__len__') else 0
    return sparse.csr_matrix((n,0), dtype=np.float32)

ROOT=Path.cwd(); TODAY=os.environ.get('TODAY') or __import__('datetime').date.today().isoformat()
INTENT=Path(os.environ['INTENT_PKL']); SPAM=Path(os.environ['SPAM_PKL']); KIE=Path(os.environ['KIE_DIR'])
def save(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2),'utf-8')

# ===== Intent：dict['pipeline'] 直接推論 =====
I=ROOT/f'models/intent/artifacts/v{TODAY}'; I.mkdir(parents=True,exist_ok=True)
im={}
try:
    obj=joblib.load(INTENT)
    pipe=obj['pipeline'] if isinstance(obj,dict) and 'pipeline' in obj else None
    assert isinstance(pipe, Pipeline), 'intent: pipeline missing or not a Pipeline'
    X,y=[],[]
    for ln in (ROOT/'data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
        if not ln.strip(): continue
        j=json.loads(ln); X.append(j.get('text','')); y.append(j.get('label',''))
    pred=pipe.predict(X)
    rep=classification_report(y, pred, output_dict=True, zero_division=0)
    im={'classification_report':rep,'source':'dict.pipeline','note':'__main__.rules_feat shim active (zero-width)'}
except Exception as e:
    im={'status':'error','error':str(e)[:1000]}
save(I/'metrics.json', im)

# ===== Spam：依你資產（非 Pipeline）→ 標註不可評 =====
S=ROOT/f'models/spam/artifacts/v{TODAY}'; S.mkdir(parents=True,exist_ok=True)
sm={}
try:
    obj=joblib.load(SPAM)
    sm={'status':'unscorable','reason':'asset_missing_vectorizer_or_pipeline','keys':list(obj.keys()) if isinstance(obj,dict) else str(type(obj))}
except Exception as e:
    sm={'status':'error','error':str(e)[:1000]}
save(S/'metrics.json', sm)

# ===== KIE：沿用 regex 健檢 =====
K=ROOT/f'models/kie/artifacts/v{TODAY}'; K.mkdir(parents=True,exist_ok=True)
lines=[l for l in (ROOT/'data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
rx=re.compile(r'(SO-|INV-|發票|訂單|amount|金額|電話|mobile|tel|No\.|#\d+|\b\d{2,4}[- ]?\d{3,4}\b)', re.I)
regex_ok=sum(1 for t in lines if rx.search(t))
km={'ready_flags':{'weights':(KIE/'model.safetensors').exists()}, 'regex_parse_rate': (regex_ok/len(lines) if lines else 0.0), 'n':len(lines)}
save(K/'metrics.json', km)
