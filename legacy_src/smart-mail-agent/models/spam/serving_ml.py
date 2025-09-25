from __future__ import annotations
from pathlib import Path
import joblib

ROOT = Path(__file__).resolve().parents[1]
ART  = ROOT/"spam"/"artifacts_ml"
_vec = _clf = None

def available() -> bool:
    return (ART/"vectorizer.joblib").exists() and (ART/"model.joblib").exists()

def _lazy_load():
    global _vec, _clf
    if _vec is None:
        _vec = joblib.load(ART/"vectorizer.joblib")
    if _clf is None:
        _clf = joblib.load(ART/"model.joblib")

def score_prob_spam(text: str) -> float:
    _lazy_load()
    Xv = _vec.transform([text])
    proba = getattr(_clf, "predict_proba")(Xv)[0][1]
    return float(proba)
