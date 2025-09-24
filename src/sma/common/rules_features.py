from scipy import sparse
import numpy as np
def rules_feat(texts):
    return sparse.csr_matrix((len(texts), 0), dtype=np.float32)
