from __future__ import annotations
import numpy as np
from scipy import sparse as sp
from sklearn.base import BaseEstimator, TransformerMixin
class ZeroPad(BaseEstimator, TransformerMixin):
    def __init__(self, width:int=1, dtype=np.float64, **kw):
        try: self.width = int(width) if width else 1
        except Exception: self.width = 1
        self.dtype = dtype; self._extra = dict(kw)
    def __setstate__(self, state):
        self.__dict__.update(state or {})
        if not hasattr(self,"width"): self.width=1
        if not hasattr(self,"dtype"): self.dtype=np.float64
    def fit(self, X, y=None): return self
    def transform(self, X): return sp.csr_matrix((len(X), self.width), dtype=self.dtype)
