class LabelMappingWrapper:
    def __init__(self, base, mapping):
        self.base = base
        self.mapping = {str(k): str(v) for k,v in mapping.items()}
    def predict(self, X):
        y = self.base.predict(X)
        return [ self.mapping.get(str(v), str(v)) for v in y ]
    def predict_proba(self, X):
        return self.base.predict_proba(X)
