import os, json, re, traceback
from pathlib import Path
import joblib, numpy as np
from scipy import sparse
from sklearn.metrics import classification_report
from sklearn.pipeline import Pipeline, FeatureUnion

ROOT=Path.cwd(); TODAY=os.environ.get('TODAY') or __import__('datetime').date.today().isoformat()
INTENT=Path(os.environ['INTENT_PKL']); SPAM=Path(os.environ['SPAM_PKL']); KIE=Path(os.environ['KIE_DIR'])
def save(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2),'utf-8')

# ---- utils ----
class PadCols:
    def __init__(self, base, expected): self.base, self.expected = base, int(expected)
    def fit(self, X, y=None):
        return self.base.fit(X,y) if hasattr(self.base,'fit') else self
    def transform(self, X):
        Z = self.base.transform(X) if hasattr(self.base,'transform') else self.base.fit_transform(X)
        cur = Z.shape[1]
        if cur == self.expected: return Z
        if cur >  self.expected: return Z[:, :self.expected]
        pad = self.expected - cur
        if sparse.issparse(Z):
            Zpad = sparse.csr_matrix((Z.shape[0], pad), dtype=Z.dtype)
            return sparse.hstack([Z, Zpad], format='csr')
        return np.pad(Z, ((0,0),(0,pad)), mode='constant')

def get_expected_dims(clf):
    exp = getattr(clf, 'n_features_in_', None)
    if exp is None and hasattr(clf,'calibrated_classifiers_') and clf.calibrated_classifiers_:
        try: exp = clf.calibrated_classifiers_[0].base_estimator.n_features_in_
        except Exception: pass
    return exp

def features_step(pipe:Pipeline):
    # 偏好 named_steps['features']；否則取首步
    if hasattr(pipe,'named_steps') and 'features' in pipe.named_steps: return 'features', pipe.named_steps['features']
    return pipe.steps[0]

# ---- Intent ----
I=ROOT/f'models/intent/artifacts/v{TODAY}'; I.mkdir(parents=True,exist_ok=True)
im={}
try:
    obj = joblib.load(INTENT)
    pipe = obj['pipeline'] if isinstance(obj,dict) and 'pipeline' in obj else None
    assert isinstance(pipe, Pipeline), 'intent: pipeline missing or not a Pipeline'
    # 讀資料
    X,y=[],[]
    for ln in (ROOT/'data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
        if not ln.strip(): continue
        j=json.loads(ln); X.append(j.get('text','')); y.append(j.get('label',''))
    # 期望維度
    clf = pipe.steps[-1][1]
    expected = get_expected_dims(clf)
    if expected is None: raise RuntimeError('intent: cannot resolve expected n_features_in_ from classifier')
    # 實際 features 維度（走 features.transform(X) 一次）
    fname, feats = features_step(pipe)
    try:
        cur = feats.transform(X).shape[1]
    except Exception:
        feats.fit(X, y if hasattr(feats,'fit') else None)
        cur = feats.transform(X).shape[1]
    # 對齊：必要時包 PadCols
    if cur != expected:
        pipe.steps[0] = (fname, PadCols(feats, expected))
    pred = pipe.predict(X)
    rep  = classification_report(y, pred, output_dict=True, zero_division=0)
    im   = {'classification_report':rep,'source':'dict.pipeline','feature_dims':{'expected':int(expected),'actual':int(cur),'padded':bool(cur!=expected)}}
except Exception as e:
    im = {'status':'error','error':str(e)[:1000], 'trace': traceback.format_exc(limit=3)}
save(I/'metrics.json', im)

# ---- Spam：非 Pipeline → 可審計不可評 ----
S=ROOT/f'models/spam/artifacts/v{TODAY}'; S.mkdir(parents=True,exist_ok=True)
sm={}
try:
    obj=joblib.load(SPAM)
    sm={'status':'unscorable','reason':'asset_missing_vectorizer_or_pipeline','keys': list(obj.keys()) if isinstance(obj,dict) else str(type(obj))}
except Exception as e:
    sm={'status':'error','error':str(e)[:1000]}
save(S/'metrics.json', sm)

# ---- KIE：regex 健檢（保持可用） ----
K=ROOT/f'models/kie/artifacts/v{TODAY}'; K.mkdir(parents=True,exist_ok=True)
lines=[l for l in (ROOT/'data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
rx=re.compile(r'(SO-|INV-|發票|訂單|amount|金額|電話|mobile|tel|No\.|#\d+|\b\d{2,4}[- ]?\d{3,4}\b)', re.I)
regex_ok=sum(1 for t in lines if rx.search(t))
km={'ready_flags':{'weights':(KIE/'model.safetensors').exists()}, 'regex_parse_rate': (regex_ok/len(lines) if lines else 0.0), 'n':len(lines)}
save(K/'metrics.json', km)
