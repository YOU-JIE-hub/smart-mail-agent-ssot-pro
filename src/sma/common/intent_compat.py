import os, sys, json, types, traceback, re
from typing import Any, Dict, List, Tuple, Optional
import numpy as np
from scipy import sparse
import joblib
from sklearn.pipeline import Pipeline

_pipe = None        # type: ignore
_classes: List[str] = []
_loaded_path: Optional[str] = None

def _prepare_rules_feat_stub():
    """把 rules_feat 注入到 __main__ 與 rules_features，解除 pickled 依賴。"""
    try:
        from sma.common.rules_features import rules_feat as _rf
    except Exception:
        def _rf(texts): return sparse.csr_matrix((len(texts),0), dtype=np.float32)
    # 注入 __main__
    m = sys.modules.get("__main__")
    if m is not None and not hasattr(m, "rules_feat"):
        setattr(m, "rules_feat", _rf)
    # 注入 rules_features 模組
    if "rules_features" not in sys.modules:
        mod = types.ModuleType("rules_features")
        mod.rules_feat = _rf
        sys.modules["rules_features"] = mod

class _PadCSRColumns:
    """把 CSR 特徵矩陣列數對齊到指定維度（不足補零、超過截斷）。"""
    def __init__(self, target_dim: int): self.target_dim = target_dim
    def fit(self, X, y=None): return self
    def transform(self, X):
        if not sparse.issparse(X): return X
        n = X.shape[1]
        if n == self.target_dim: return X
        if n < self.target_dim:
            pad = sparse.csr_matrix((X.shape[0], self.target_dim - n), dtype=X.dtype)
            return sparse.hstack([X, pad], format="csr")
        return X[:, :self.target_dim]

def _clf_expected_dim(clf) -> Optional[int]:
    # CalibratedClassifierCV -> base_estimator
    if hasattr(clf, "calibrated_classifiers_") and getattr(clf, "calibrated_classifiers_"):
        try: return int(getattr(getattr(clf.calibrated_classifiers_[0], "base_estimator"), "n_features_in_", None) or 0) or None
        except Exception: return None
    # OneVsRest/LogReg/SVC...
    return getattr(clf, "n_features_in_", None)

def load_pipeline(pkl_path: str) -> Dict[str, Any]:
    global _pipe, _classes, _loaded_path
    _prepare_rules_feat_stub()
    raw = joblib.load(pkl_path)
    pipe = raw.get("pipeline") if isinstance(raw, dict) and "pipeline" in raw else raw
    # 嘗試擷取 classes_
    classes: List[str] = []
    if isinstance(pipe, Pipeline):
        clf = pipe.steps[-1][1]
        if hasattr(clf, "classes_"):
            try: classes = list(clf.classes_)
            except Exception: classes = []
        # 若維度不符 → 注入 PadShim 到 tfidf 後面
        need = _clf_expected_dim(clf)
        try:
            Xt = pipe.steps[-2][1]  # 常見 'tfidf'
            # 只有在需要時才安插 pad
            if isinstance(need, int) and need > 0:
                # 在 tfidf 後安插 pad（不破壞原始步驟）
                new_steps = []
                inserted = False
                for name, est in pipe.steps:
                    new_steps.append((name, est))
                    if name != pipe.steps[-1][0] and not inserted and name.lower().startswith("tfidf"):
                        new_steps.append(("_padshim", _PadCSRColumns(need)))
                        inserted = True
                if inserted: pipe = Pipeline(new_steps)
        except Exception:
            pass

    _pipe = pipe
    _classes = classes
    _loaded_path = pkl_path
    return meta()

def _normalize_proba(P, n_samples):
    # list-of-arrays -> 堆成 (n_samples, n_classes)
    if isinstance(P, list):
        P = np.column_stack([np.asarray(a).reshape(-1) for a in P])
    P = np.asarray(P)
    # 1D（二元）-> [1-p, p]
    if P.ndim == 1:
        p = P.astype(float).ravel()
        P = np.column_stack([1.0 - p, p])
    # (n_classes, n_samples) -> 轉置
    if P.shape[0] != n_samples and P.shape[1] == n_samples:
        P = P.T
    return P.astype(float, copy=False)

def predict_proba_batch(texts: List[str]) -> Tuple[np.ndarray, List[str]]:
    """永遠回 (n_samples, n_classes)。遇到 N!=M 的特徵錯配時，動態補零到期望維度。"""
    if _pipe is None:
        raise RuntimeError("pipeline not loaded; call load_pipeline(path) first")
    try:
        P = _pipe.predict_proba(texts)
        return _normalize_proba(P, len(texts)), (_classes or [])
    except Exception as e:
        msg = str(e)
        m = re.search(r"X has (\d+) features,.*?(\d+)", msg)
        if not m or not isinstance(_pipe, Pipeline):
            raise
        have, need = int(m.group(1)), int(m.group(2))
        prior = Pipeline(_pipe.steps[:-1])
        clf   = _pipe.steps[-1][1]
        X = prior.transform(texts)
        # pad / truncate
        if X.shape[1] < need:
            zeros = sparse.csr_matrix((X.shape[0], need - X.shape[1]), dtype=X.dtype)
            X = sparse.hstack([X, zeros], format="csr")
        elif X.shape[1] > need:
            X = X[:, :need]
        P = clf.predict_proba(X)
        return _normalize_proba(P, len(texts)), (_classes or [])

def meta() -> Dict[str, Any]:
    return {
        "path": _loaded_path,
        "raw_type": type(_pipe).__name__ if _pipe is not None else None,
        "raw_desc": repr(_pipe)[:400] if _pipe is not None else None,
        "extracted_from": "root_or_dict[pipeline]",
        "classes_": _classes,
    }
