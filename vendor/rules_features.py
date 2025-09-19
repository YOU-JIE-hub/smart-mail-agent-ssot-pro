from __future__ import annotations
import regex as re
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.base import BaseEstimator, TransformerMixin

__RULES_VERSION__ = 'v1.0.0-fixed7'
_re_money = re.compile(r'(?:(?:NT\$|TWD|\$)\s*\d[\d,]*(?:\.\d{1,2})?)',re.I)
_re_phone = re.compile(r'(?:\+?886[-\s]?|0)\d{1,2}[-\s]?\d{3,4}[-\s]?\d{3,4}')
_re_order = re.compile(r'\b(?:SO|PO|ORD|INV)[-_]?[A-Z0-9]{3,}\b')
_re_qty   = re.compile(r'\b(?:qty|數量|共)\s*\d+\b',re.I)
_re_cn    = re.compile(r'\p{Han}')  # 任意中文
_re_email = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

class RulesFeatTransformer(BaseEstimator, TransformerMixin):
    def __init__(self): pass
    def fit(self, X, y=None): return self
    def transform(self, X):
        rows, cols, data = [], [], []
        for i, t in enumerate(X):
            s = t or ''
            f = [
                1.0 if _re_money.search(s) else 0.0,
                1.0 if _re_phone.search(s) else 0.0,
                1.0 if _re_order.search(s) else 0.0,
                1.0 if _re_qty.search(s) else 0.0,
                1.0 if _re_cn.search(s) else 0.0,
                float(len(s)),
                float(len(s.split()))
            ]
            for j,v in enumerate(f):
                if v!=0.0:
                    rows.append(i); cols.append(j); data.append(v)
        return csr_matrix((data,(rows,cols)), shape=(len(X),7), dtype=np.float32)
