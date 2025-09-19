from scipy import sparse

class ZeroPad:
    def __init__(self, n_features=0, n=0, **kw):
        self.n_features = int(n_features or n or 0)
    def fit(self, X, y=None): return self
    def transform(self, X):
        n_samples = len(X)
        m = int(self.n_features)
        return sparse.csr_matrix((n_samples, m), dtype="float64")
    def get_params(self, deep=True): return {"n_features": self.n_features}
    def set_params(self, **kw):
        if "n_features" in kw: self.n_features = int(kw["n_features"])
        if "n" in kw: self.n_features = int(kw["n"])
        return self

class DictFeaturizer:
    def __init__(self, **kw): pass
    def fit(self, X, y=None): return self
    def transform(self, X):  # 回傳 0 欄位 CSR，能與其它特徵 hstack
        return sparse.csr_matrix((len(X), 0), dtype="float64")
    def get_params(self, deep=True): return {}
    def set_params(self, **kw): return self
