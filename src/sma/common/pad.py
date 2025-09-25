from typing import Optional
import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin

class PadColumns(BaseEstimator, TransformerMixin):
    def __init__(self, n_extra: int = 0):
        self.n_extra = int(n_extra)

    def fit(self, X, y: Optional[np.ndarray] = None):
        return self

    def transform(self, X):
        n_extra = int(getattr(self, "n_extra", 0) or 0)
        if n_extra <= 0:
            return X
        n = X.shape[0]
        if sparse.issparse(X):
            zeros = sparse.csr_matrix((n, n_extra), dtype=X.dtype)
            return sparse.hstack([X, zeros], format="csr")
        else:
            import numpy as np
            zeros = np.zeros((n, n_extra), dtype=X.dtype)
            return np.hstack([X, zeros])
