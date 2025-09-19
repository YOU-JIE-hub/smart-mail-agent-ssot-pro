from __future__ import annotations
import os,json,random
from pathlib import Path
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from joblib import dump
from vendor.rules_features import RulesFeatTransformer, __RULES_VERSION__
from scripts.common_io import read_jsonl, ensure_registry, write_json, sha256_head

ROOT=Path(os.getcwd()); random.seed(42)
DATE=os.environ.get('TODAY','')
ART=ROOT/'models'/'intent'/'artifacts'/f'v{DATE}'
ART.mkdir(parents=True, exist_ok=True)
train_p = ROOT/'data'/'intent_eval'/'dataset.cleaned.jsonl'  # 使用你現有檔名作為基線資料源
rows=read_jsonl(train_p)
X=[r.get('text','') for r in rows]; y=[r.get('label','') for r in rows]
Xtr,Xte,ytr,yte = train_test_split(X,y,test_size=0.2,random_state=42,stratify=y if len(set(y))>1 else None)
union = FeatureUnion([('tfidf_w', TfidfVectorizer(ngram_range=(1,2), min_df=1, sublinear_tf=True)),
                      ('tfidf_c', TfidfVectorizer(analyzer='char', ngram_range=(3,5), min_df=1, sublinear_tf=True)),
                      ('rules',   RulesFeatTransformer())])
svc = LinearSVC(random_state=42)
clf = CalibratedClassifierCV(svc, method='sigmoid', cv=5)
pipe = Pipeline([('features', union), ('clf', clf)])
pipe.fit(Xtr, ytr)
pred = pipe.predict(Xte)
rep = classification_report(yte, pred, output_dict=True, zero_division=0)
meta={'date':DATE,'data_path':str(train_p),'n_total':len(rows),'rules_version':__RULES_VERSION__}
dump({'pipeline':pipe,'meta':meta}, ART/'model.pkl', compress=3, protocol=5)
write_json(ART/'metrics.json', {'classification_report':rep})
write_json(ART/'thresholds.json', {'note':'intent uses calibrated probabilities; threshold decided in router'})
(ART/'MODEL_CARD.md').write_text('# Model Card — Intent\n- Algo: LinearSVC + CalibratedCV\n- Features: TFIDF(word,char)+rules(7)\n', 'utf-8')
write_json(ART/'training_meta.json', meta)
write_json(ART/'filesha.json', {'model.pkl': sha256_head(ART/'model.pkl')})
ensure_registry('intent', f'v{DATE}')
print('[OK] intent trained ->', ART.as_posix())
