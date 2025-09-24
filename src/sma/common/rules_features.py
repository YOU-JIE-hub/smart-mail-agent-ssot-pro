from scipy import sparse
import numpy as np
def rules_feat(texts):
    # 訓練時規則維度未知，交由 PadShim 對齊到 clf.n_features_in_
    return sparse.csr_matrix((len(texts), 0), dtype=np.float32)
