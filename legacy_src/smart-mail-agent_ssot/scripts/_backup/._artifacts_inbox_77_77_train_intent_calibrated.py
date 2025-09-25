import json, joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

def load(p): return [json.loads(l) for l in open(p, encoding="utf-8")]
tr=load("data/intent/train.jsonl"); va=load("data/intent/val.jsonl"); te=load("data/intent/test.jsonl")
Xtr=[o["text"] for o in tr]; ytr=[o["label"] for o in tr]
Xva=[o["text"] for o in va]; yva=[o["label"] for o in va]
Xte=[o["text"] for o in te]; yte=[o["label"] for o in te]

base=Pipeline([("tfidf",TfidfVectorizer(ngram_range=(1,2),min_df=2,max_features=100000)),
               ("clf",LinearSVC())])
cal=CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3).fit(Xtr,ytr)

Path("reports_auto").mkdir(exist_ok=True)
def eval_split(name,X,y):
    yp=cal.predict(X)
    acc=accuracy_score(y,yp)
    Path("reports_auto", f"intent_{name}_report.txt").write_text(
        classification_report(y, yp, digits=4), encoding="utf-8")
    print(f"[{name}] acc={acc:.4f}")
eval_split("val", Xva, yva)
eval_split("test", Xte, yte)

Path("artifacts").mkdir(exist_ok=True)
joblib.dump(cal, "artifacts/intent_pro_cal.pkl")
print("[MODEL] artifacts/intent_pro_cal.pkl")
