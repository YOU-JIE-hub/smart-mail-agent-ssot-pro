import numpy as np
class rules_feat:
    def __init__(self,*a,**k): self.n_features_=k.get("n_features_",1)
    def fit(self,X,y=None): return self
    def transform(self,X):
        n=len(X) if hasattr(X,"__len__") else 1
        d=int(self.n_features_) if isinstance(self.n_features_,int) else 1
        try: return np.zeros((n,d))
        except: return np.zeros((n,1))
