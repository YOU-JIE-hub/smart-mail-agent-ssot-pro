from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import json, joblib

ROOT = Path(__file__).resolve().parents[1]
ART  = ROOT/"intent"/"artifacts_ml"
_vec = _clf = _labels = None

def available() -> bool:
    return (ART/"vectorizer.joblib").exists() and (ART/"model.joblib").exists() and (ART/"labels.json").exists()

def _lazy_load():
    global _vec, _clf, _labels
    if _vec is None:
        _vec = joblib.load(ART/"vectorizer.joblib")
    if _clf is None:
        _clf = joblib.load(ART/"model.joblib")
    if _labels is None:
        _labels = json.loads((ART/"labels.json").read_text(encoding="utf-8"))

def predict(text: str) -> Dict[str, Any]:
    _lazy_load()
    Xv = _vec.transform([text])
    prob = getattr(_clf, "predict_proba", None)
    if prob:
        p = prob(Xv)[0]
        top = int(p.argmax())
    else:
        top = int(_clf.predict(Xv)[0])
        p = None
    label = _labels[top] if top < len(_labels) else "other"
    intents = [label]
    if label == "biz_quote": intents += ["sales","quote"]
    return {"intents": intents, "labels": [label], "length": len(text.split()), "probs": p.tolist() if p is not None else None}
