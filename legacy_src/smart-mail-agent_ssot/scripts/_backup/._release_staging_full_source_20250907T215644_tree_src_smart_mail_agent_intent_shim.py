#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/intent/shim.py
# 模組用途
#   joblib 反序列化時的 __main__ 名稱相容 shims。
from __future__ import annotations

import sys
import types

import numpy as np
from scipy import sparse  # noqa: F401


def _width(x) -> int:
    """參數: 任意；回傳: 合理寬度（>=1）。"""
    import numpy as _np

    if x is None:
        return 1
    for t in (int, float):
        if isinstance(x, t):
            return max(int(x), 1)
    if isinstance(x, _np.generic):
        try:
            return max(int(x), 1)
        except Exception:
            return 1
    if isinstance(x, (list, tuple, dict, set, _np.ndarray)):  # noqa: UP038
        try:
            return max(int(len(x)), 1)
        except Exception:
            return 1
    return 1


def _zeros2d(n: int, k: int):
    return sparse.csr_matrix((n, max(k, 1)), dtype=np.float32)


class rules_feat:  # noqa: N801
    def __init__(self, n_features: int = 1, **kw) -> None:
        self.n_features = _width(n_features)

    def fit(self, X, y=None):  # noqa: N803
        self._out = self.n_features
        return self

    def transform(self, X):  # noqa: N803  # noqa: N803
        X = list(X)  # noqa: N806
        return _zeros2d(len(X), getattr(self, "_out", self.n_features))

    def get_feature_names_out(self, input_features=None):  # noqa: ARG002
        k = getattr(self, "_out", self.n_features)
        return np.array([f"rule_{i}" for i in range(k)], dtype=object)


class ZeroPad:
    def __init__(self, width: int = 1, **kw) -> None:
        self.width = _width(width)

    def fit(self, X, y=None):  # noqa: N803
        self._out = self.width
        return self

    def transform(self, X):  # noqa: N803  # noqa: N803
        X = list(X)  # noqa: N806
        return _zeros2d(len(X), getattr(self, "_out", self.width))

    def get_feature_names_out(self, input_features=None):  # noqa: ARG002
        k = getattr(self, "_out", self.width)
        return np.array([f"zeropad_{i}" for i in range(k)], dtype=object)


class DictFeaturizer:
    def __init__(self, keys=None, **kw) -> None:
        self.keys = list(keys) if keys else []

    def fit(self, X, y=None):  # noqa: N803
        self._out = max(len(self.keys), 1)
        return self

    def transform(self, X):  # noqa: N803  # noqa: N803
        X = list(X)  # noqa: N806
        return _zeros2d(len(X), getattr(self, "_out", max(len(self.keys), 1)))

    def get_feature_names_out(self, input_features=None):  # noqa: ARG002
        k = getattr(self, "_out", max(len(self.keys), 1))
        return np.array([f"dict_{i}" for i in range(k)], dtype=object)


def _ensure(mod):
    for n, o in {"rules_feat": rules_feat, "ZeroPad": ZeroPad, "DictFeaturizer": DictFeaturizer}.items():
        if not hasattr(mod, n):
            setattr(mod, n, o)


def ensure_joblib_main_shims() -> None:
    """參數: 無；回傳: 無。將必要類註冊到 __main__ 與 e2e 命名空間。"""
    m = sys.modules.get("__main__") or types.ModuleType("__main__")
    sys.modules["__main__"] = m
    _ensure(m)
    t = sys.modules.get("smart_mail_agent.cli.e2e") or types.ModuleType("smart_mail_agent.cli.e2e")
    sys.modules["smart_mail_agent.cli.e2e"] = t
    _ensure(t)
