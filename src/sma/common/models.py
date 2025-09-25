from __future__ import annotations
import os, json
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from .pathing import env_path

# scikit-learn / joblib
try:
    import joblib  # type: ignore
except Exception:
    joblib = None  # type: ignore

# transformers（KIE）
try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification  # type: ignore
except Exception:
    AutoTokenizer = AutoModelForTokenClassification = None  # type: ignore

def load_joblib_pipeline(env_name: str, default_rel: Optional[str]) -> Any:
    if joblib is None:
        raise RuntimeError("joblib not available in environment")
    p = env_path(env_name, default_rel)
    if not p or not p.exists():
        raise FileNotFoundError(f"model not found for {env_name} (resolved={p})")
    return joblib.load(p)

def load_kie_from_dir(env_name: str = "KIE_DIR", default_rel: Optional[str] = None):
    if AutoTokenizer is None or AutoModelForTokenClassification is None:
        raise RuntimeError("transformers not available in environment")
    d = env_path(env_name, default_rel)
    if not d or not d.exists():
        raise FileNotFoundError(f"KIE dir not found for {env_name} (resolved={d})")
    tok = AutoTokenizer.from_pretrained(str(d), use_fast=True)
    mdl = AutoModelForTokenClassification.from_pretrained(str(d))
    mdl.eval()
    return tok, mdl

def predict_joblib(pipeline, text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"text": text}
    try:
        # 有 proba 就輸出 score，並附 label
        if hasattr(pipeline, "predict_proba"):
            proba = pipeline.predict_proba([text])[0]
            if proba.shape[-1] == 2:
                score = float(proba[1])
                label = int(score >= float(os.getenv("SMA_SPAM_THRESHOLD", "0.5")))
                out.update({"label": label, "score": score})
                return out
        # 沒有 predict_proba 就 fallback
        pred = pipeline.predict([text])[0]
        out.update({"label": int(pred)})
        return out
    except Exception as e:
        out.update({"error": f"{type(e).__name__}: {e}"})
        return out
