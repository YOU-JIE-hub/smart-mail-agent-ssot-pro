class ZeroPad:
    def __init__(self,*a,**k): pass
    def fit(self,X,y=None): return self
    def transform(self,X): return X
    def fit_transform(self,X,y=None): return X
