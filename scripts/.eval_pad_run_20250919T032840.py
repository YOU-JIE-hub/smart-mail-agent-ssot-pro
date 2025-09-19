import os, json, joblib, re, traceback
from pathlib import Path
import numpy as np
from scipy import sparse
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

ROOT=Path.cwd(); TODAY=os.environ.get('TODAY') or __import__('datetime').date.today().isoformat()
INTENT=Path(os.environ['INTENT_PKL']); SPAM=Path(os.environ['SPAM_PKL']); KIE=Path(os.environ['KIE_DIR'])
def save(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2),'utf-8')

# --- Intent：在 pipeline 的 features 步驟上包一層 PadCols，使輸出列數補到 clf 訓練時的 n_features_in_ ---
class PadCols:
    def __init__(self, base, expected): self.base, self.expected = base, int(expected)
    def fit(self, X, y=None):
        if hasattr(self.base,'fit'): self.base.fit(X,y)
        return self
    def transform(self, X):
        Z = self.base.transform(X) if hasattr(self.base,'transform') else self.base.fit_transform(X)
        # 稀疏補零列到 expected 維
        cur = Z.shape[1]
        if cur == self.expected: return Z
        if cur > self.expected: return Z[:, :self.expected]
        pad = self.expected - cur
        if sparse.issparse(Z):
            Zpad = sparse.csr_matrix((Z.shape[0], pad), dtype=Z.dtype)
            return sparse.hstack([Z, Zpad], format='csr')
        import numpy as _np
        return _np.pad(Z, ((0,0),(0,pad)), mode='constant')

def patch_intent_pipeline(pipe):
    # 取得分類器的訓練特徵維度（CalibratedClassifierCV 包 SVC/LinearSVC）
    clf = pipe.steps[-1][1]
    exp = getattr(clf, 'n_features_in_', None)
    if exp is None and hasattr(clf,'calibrated_classifiers_') and clf.calibrated_classifiers_:
        try: exp = clf.calibrated_classifiers_[0].base_estimator.n_features_in_
        except Exception: pass
    if exp is None: raise RuntimeError('intent: cannot resolve expected n_features_in_ from classifier')
    name0, feat = pipe.steps[0]
    pipe.steps[0] = (name0, PadCols(feat, exp))
    return exp

# ====== 寫指標：Intent ======
I=ROOT/f'models/intent/artifacts/v{TODAY}'; I.mkdir(parents=True,exist_ok=True)
im={}
try:
    obj=joblib.load(INTENT)
    pipe=obj['pipeline'] if isinstance(obj,dict) and 'pipeline' in obj else None
    assert isinstance(pipe, Pipeline), 'intent: pipeline missing or not a Pipeline'
    expected = patch_intent_pipeline(pipe)
    X,y=[],[]
    for ln in (ROOT/'data/intent_eval/dataset.cleaned.jsonl').read_text('utf-8').splitlines():
        if not ln.strip(): continue
        j=json.loads(ln); X.append(j.get('text','')); y.append(j.get('label',''))
    pred = pipe.predict(X)
    rep  = classification_report(y, pred, output_dict=True, zero_division=0)
    im   = {'classification_report':rep,'source':'dict.pipeline+PadCols','expected_features':int(expected)}
except Exception as e:
    im   = {'status':'error','error':str(e)[:1000], 'trace': traceback.format_exc(limit=3)}
save(I/'metrics.json', im)

# ====== 寫指標：Spam（你這顆只有 LR 本體，無向量器 → 不可評） ======
S=ROOT/f'models/spam/artifacts/v{TODAY}'; S.mkdir(parents=True,exist_ok=True)
sm={}
try:
    obj=joblib.load(SPAM)
    sm={'status':'unscorable','reason':'asset_missing_vectorizer_or_pipeline','keys': list(obj.keys()) if isinstance(obj,dict) else str(type(obj))}
except Exception as e:
    sm={'status':'error','error':str(e)[:1000]}
save(S/'metrics.json', sm)

# ====== 寫指標：KIE（regex 健檢） ======
K=ROOT/f'models/kie/artifacts/v{TODAY}'; K.mkdir(parents=True,exist_ok=True)
lines=[l for l in (ROOT/'data/kie_eval/gold_merged.jsonl').read_text('utf-8').splitlines() if l.strip()]
rx=re.compile(r'(SO-|INV-|發票|訂單|amount|金額|電話|mobile|tel|No\.|#\d+|\b\d{2,4}[- ]?\d{3,4}\b)', re.I)
regex_ok=sum(1 for t in lines if rx.search(t))
km={'ready_flags':{'weights':(KIE/'model.safetensors').exists()}, 'regex_parse_rate': (regex_ok/len(lines) if lines else 0.0), 'n':len(lines)}
save(K/'metrics.json', km)
