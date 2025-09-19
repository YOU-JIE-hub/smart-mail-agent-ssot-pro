# -*- coding: utf-8 -*-
from typing import List
import re
import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin

class RulesFeatV1(BaseEstimator, TransformerMixin):
    """
    穩定版規則特徵（v1）：固定 7 維，順序與語義不可變更
    0: has_biz_quote        1: has_tech_support   2: has_complaint
    3: has_profile_update   4: has_policy_qa      5: has_amount
    6: has_contact_hint (phone/email)
    """
    VERSION = "v1"
    FEATURES = [
        "has_biz_quote","has_tech_support","has_complaint",
        "has_profile_update","has_policy_qa","has_amount","has_contact_hint"
    ]
    _PATTERNS = {
        "has_biz_quote":      [r"報價", r"詢價", r"\bquote\b", r"報.*?(?:金額|價格)"],
        "has_tech_support":   [r"壞了|故障", r"無法(啟動|登入|使用)", r"連不上", r"維修|RMA", r"技術(支援|問題)"],
        "has_complaint":      [r"抱怨|投訴|客訴", r"太慢|沒回覆|延遲", r"品質.*?問題"],
        "has_profile_update": [r"更新(資料|地址|電話|抬頭)", r"變更(聯絡|公司|抬頭|地址|電話)", r"修改(資料|資訊)"],
        "has_policy_qa":      [r"保固|保修|維修條款", r"退換貨|退貨|換貨", r"\bSLA\b|服務水準", r"付款方式", r"發票"],
        "has_amount":         [r"(?:\$|NTD?\s*|新台幣)\s*[0-9][\d,\.]*|[0-9][\d,\.]*\s*元"],
        "has_contact_hint":   [r"\b\d{9,}\b", r"\b09\d{8}\b", r"@"]
    }
    def __init__(self):
        self._compiled = {k: [re.compile(p, re.I) for p in ps] for k, ps in self._PATTERNS.items()}
    def fit(self, X: List[str], y=None): return self
    def transform(self, X: List[str]):
        rows, cols, data = [], [], []
        for i, text in enumerate(X):
            t = text if isinstance(text, str) else str(text or "")
            for j, feat in enumerate(self.FEATURES):
                if any(r.search(t) for r in self._compiled[feat]):
                    rows.append(i); cols.append(j); data.append(1.0)
        return sparse.csr_matrix((data, (rows, cols)), shape=(len(X), len(self.FEATURES)))
    def get_feature_names_out(self, input_features=None):
        return np.array(self.FEATURES, dtype=object)
