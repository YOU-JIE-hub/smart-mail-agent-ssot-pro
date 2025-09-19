from scipy import sparse
class ZeroPad:
    def __init__(self, n_features: int = 0): self.n_features=int(n_features)
    def fit(self, X, y=None): return self
    def transform(self, X):
        n = len(X) if hasattr(X,"__len__") else X.shape[0]
        return sparse.csr_matrix((n, self.n_features), dtype="float64")
    def get_params(self, deep=True): return {"n_features": self.n_features}
    def set_params(self, **kw):
        if "n_features" in kw: self.n_features=int(kw["n_features"]); return self
