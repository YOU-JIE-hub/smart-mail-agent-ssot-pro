import os, sys, json, traceback, types
from typing import Any, Dict, List, Tuple, Optional
import numpy as np
from scipy import sparse
import joblib

_pipe = None
_classes: List[str] = []

def _inject_rules_feat():
    try:
        # 若 __main__ 沒有 rules_feat，注入一個 0 維的 placeholder（避免 unpickle 找不到）
        if not hasattr(sys.modules.get("__main__"), "rules_feat"):
            from sma.common import rules_features as rf
            sys.modules["__main__"] = sys.modules.get("__main__", types.ModuleType("__main__"))
            setattr(sys.modules["__main__"], "rules_feat", getattr(rf, "rules_feat"))
    except Exception:
        pass

class _PadCSRColumns:
    def __init__(self, target_dim: int):
        self.target_dim = int(target_dim)
    def fit(self, X, y=None): return self
    def transform(self, X):
        if not sparse.issparse(X): return X
        cur = X.shape[1]
        if cur >= self.target_dim: return X
        pad = sparse.csr_matrix((X.shape[0], self.target_dim - cur), dtype=X.dtype)
        return sparse.hstack([X, pad], format="csr")

def _clf_expected_dim(clf) -> Optional[int]:
    for c in (clf, getattr(clf, "base_estimator", None)):
        if c is not None and hasattr(c, "n_features_in_"):
            try: return int(getattr(c, "n_features_in_"))
            except Exception: pass
    return None

def _get_classes_from_pipe(p) -> List[str]:
    # 優先：末端分類器的 classes_
    try:
        from sklearn.pipeline import Pipeline
        if isinstance(p, Pipeline):
            clf = p.steps[-1][1]
            if hasattr(clf, "classes_"):
                arr = getattr(clf, "classes_")
                return arr.tolist() if hasattr(arr, "tolist") else list(arr)
    except Exception:
        pass
    # 備援：ENV
    try:
        raw = os.getenv("INTENT_CLASSES_JSON")
        if raw:
            val = json.loads(raw)
            return list(val)
    except Exception:
        pass
    return []

def load_pipeline(pkl_path: str) -> None:
    global _pipe, _classes
    _inject_rules_feat()
    raw = joblib.load(pkl_path)
    pipe = raw.get("pipeline") if isinstance(raw, dict) else raw

    # 若是 sklearn Pipeline，插入 PadShim 在最後一層 clf 前面（用 clf.n_features_in_）
    try:
        from sklearn.pipeline import Pipeline
        if isinstance(pipe, Pipeline):
            steps = list(pipe.steps)
            clf = steps[-1][1]
            tgt = _clf_expected_dim(clf)
            if tgt:
                steps.insert(-1, ("_padshim", _PadCSRColumns(tgt)))
                pipe = Pipeline(steps)
    except Exception:
        pass

    _pipe = pipe
    _classes = _get_classes_from_pipe(pipe)
    # 確保是 list，且避免 numpy array 觸發 ambiguous truth
    if _classes is None: _classes = []
    _classes = list(_classes)

def meta() -> Dict[str, Any]:
    return {"path": os.getenv("INTENT_PKL"), "classes_": list(_classes)}

def predict_proba_batch(texts: List[str]) -> Tuple[np.ndarray, List[str]]:
    if _pipe is None:
        raise RuntimeError("pipeline not loaded; call load_pipeline(path) first")
    proba = _pipe.predict_proba(texts)
    # 可能是 list-of-arrays（OvR/Calibrated）、或 1D、或轉置
    if isinstance(proba, list):
        proba = np.column_stack([np.ravel(x).astype(float) for x in proba])
    proba = np.asarray(proba, dtype=float)
    if proba.ndim == 1:
        p = proba.ravel()
        proba = np.column_stack([1.0 - p, p])
    if proba.shape[0] != len(texts) and proba.shape[1] == len(texts):
        proba = proba.T
    return proba, list(_classes)
