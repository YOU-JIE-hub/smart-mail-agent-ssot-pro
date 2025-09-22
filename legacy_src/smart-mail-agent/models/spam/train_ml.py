from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import json, joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
ART  = ROOT/"spam"/"artifacts_ml"
DATA = ROOT/"spam"/"data"
ART.mkdir(parents=True, exist_ok=True)

def _read_jsonl(p: Path) -> List[Dict]:
    if not p.exists(): return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

def _load_data() -> List[Dict]:
    xs = _read_jsonl(DATA/"train.jsonl")
    if xs: return xs
    # minimal fallback
    return [{"text":"free money now","label":"spam"},{"text":"想洽談合作與報價","label":"ham"}]

def train():
    rows = _load_data()
    X = [r["text"] for r in rows]
    y = [1 if r["label"]=="spam" else 0 for r in rows]

    vec = TfidfVectorizer(ngram_range=(1,2), min_df=1)
    Xv  = vec.fit_transform(X)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(Xv, y)

    joblib.dump(vec, ART/"vectorizer.joblib")
    joblib.dump(clf, ART/"model.joblib")
    return {"ok": True, "artifact_dir": str(ART)}

if __name__ == "__main__":
    import json as _j; print(_j.dumps(train(), ensure_ascii=False))
