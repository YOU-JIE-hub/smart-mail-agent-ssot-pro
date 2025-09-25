#!/usr/bin/env python3
# 檔案位置：src/smart_mail_agent/ml/rules6_padder.py
# 模組用途：提供可被 joblib 安全載入的 Transformer，將文字轉為「向量器特徵 + 6 維規則特徵」，並補齊到分類器期望寬度
from __future__ import annotations
from typing import List, Optional, Sequence
import re
import numpy as np
from scipy import sparse as sp
from sklearn.base import BaseEstimator, TransformerMixin

_KW = {
    "biz_quote": ("報價","報價單","估價","quote","quotation","estimate"),
    "tech_support": ("錯誤","無法","壞掉","當機","crash","error","bug","exception","log","連不上","卡住"),
    "complaint": ("抱怨","投訴","退費","不滿","差勁","延誤","拖延","沒人回","客服太慢"),
    "policy_qa": ("隱私","政策","條款","合約","dpa","gdpr","資安","法遵","合規","續約","nda"),
    "profile_update": ("變更","更新","修改","變更資料","帳號","密碼","email","電話","地址"),
}
_RE_URL = re.compile(r"https?://|\.(zip|exe|js|vbs|bat|cmd|lnk|iso|docm|xlsm|pptm)\b", re.I)

def _rules6(texts: Sequence[str]) -> sp.csr_matrix:
    rows, cols, data = [], [], []
    for i, t in enumerate(texts):
        tl = (t or "").lower()
        j = 0
        for key in ("biz_quote","tech_support","complaint","policy_qa","profile_update"):
            if any(k in tl for k in _KW[key]):
                rows.append(i); cols.append(j); data.append(1.0)
            j += 1
        if _RE_URL.search(tl):
            rows.append(i); cols.append(j); data.append(1.0)
    n = len(texts)
    return sp.csr_matrix((data,(rows,cols)), shape=(n,6), dtype="float64")

class TextRules6Featurizer(BaseEstimator, TransformerMixin):
    """
    參數
    ----
    vectorizer : 具 transform(list[str])->csr_matrix 的向量器（如 TfidfVectorizer 或 Pipeline 片段）
    expected_n_features : 分類器期望的特徵寬度（通常來自 estimator.coef_.shape[1]）
    """
    def __init__(self, vectorizer, expected_n_features: int):
        self.vectorizer = vectorizer
        self.expected_n_features = int(expected_n_features)

    def fit(self, X, y=None):
        return self

    def transform(self, X: Sequence[str]):
        # 文字向量
        if hasattr(self.vectorizer, "transform"):
            X_text = self.vectorizer.transform(X)
        else:  # 若為 Pipeline 片段但尾端非 transformer，嘗試去尾
            X_text = self.vectorizer[:-1].transform(X)  # type: ignore[index]
        # 6 維規則
        X_rules = _rules6(X)
        Xc = sp.hstack([X_text, X_rules], format="csr")
        # 寬度對齊
        cur = Xc.shape[1]
        need = self.expected_n_features
        if cur < need:
            pad = sp.csr_matrix((Xc.shape[0], need-cur), dtype="float64")
            Xc = sp.hstack([Xc, pad], format="csr")
        elif cur > need:
            Xc = Xc[:, :need]
        return Xc
