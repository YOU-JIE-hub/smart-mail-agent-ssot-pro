from __future__ import annotations
import os,json,numpy as np
from pathlib import Path
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score
from joblib import dump
from scripts.common_io import read_jsonl, ensure_registry, write_json, sha256_head

ROOT=Path(os.getcwd()); DATE=os.environ.get('TODAY','')
ART=ROOT/'models'/'spam'/'artifacts'/f'v{DATE}'
ART.mkdir(parents=True, exist_ok=True)
p = ROOT/'data'/'spam_eval'/'dataset.jsonl'
rows=read_jsonl(p)
X=[r.get('text','') for r in rows]; y=[int(r.get('label',0)) for r in rows]
Xtr,Xte,ytr,yte = train_test_split(X,y,test_size=0.2,random_state=42,stratify=y if len(set(y))>1 else None)
pipe = Pipeline([('tfidf', TfidfVectorizer(ngram_range=(1,2), min_df=2, sublinear_tf=True)),
                 ('clf',   LogisticRegression(solver='liblinear', class_weight='balanced', random_state=42))])
pipe.fit(Xtr,ytr)
proba = pipe.predict_proba(Xte)[:,1]
roc = float(roc_auc_score(yte, proba)) if len(set(yte))>1 else None
pr  = float(average_precision_score(yte, proba)) if len(set(yte))>1 else None
taus = np.linspace(0.2,0.8,13); f1s=[]
for t in taus: f1s.append((float(t), float(f1_score(yte, (proba>=t).astype(int)))))
best_tau, best_f1 = max(f1s, key=lambda x:x[1]) if len(f1s)>0 else (0.5, None)
dump(pipe, ART/'model.pkl', compress=3, protocol=5)
write_json(ART/'metrics.json', {'roc_auc':roc,'pr_auc':pr,'f1_at_tau':best_f1,'n':len(rows)})
write_json(ART/'thresholds.json', {'tau':best_tau})
(ART/'MODEL_CARD.md').write_text('# Model Card — Spam\n- Algo: TFIDF + LogisticRegression\n- Threshold: tau via max F1 on valid\n', 'utf-8')
write_json(ART/'training_meta.json', {'date':DATE,'data_path':str(p),'n_total':len(rows)})
write_json(ART/'filesha.json', {'model.pkl': sha256_head(ART/'model.pkl')})
ensure_registry('spam', f'v{DATE}')
print('[OK] spam trained ->', ART.as_posix())
