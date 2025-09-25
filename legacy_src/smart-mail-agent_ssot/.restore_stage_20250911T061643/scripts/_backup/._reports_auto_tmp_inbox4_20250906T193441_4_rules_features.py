# -*- coding: utf-8 -*-
from typing import List
import numpy as np
from scipy import sparse

API_TERMS    = ["api","sdk","rest","swagger","endpoint","token","webhook","api 文件","sdk","整合"]
POLICY_TERMS = ["dpa","data processing","cross-border","renew","expiry","assignment","處理者附錄","跨境","到期","續約","刪除","資料保存"]
ERROR_TERMS  = ["error","fail","cannot","timeout","429","5xx","saml","ntp","錯誤","失敗","無法","逾時","502","503","504"]
PRICE_TERMS  = ["quote","price","pricing","tco","sow","報價","總價","折扣","年費","專案價","tco"]
PROFILE_TERMS= ["contact","sms","phone","更新聯絡人","更新電話","update contact","alert list"]

def _hits(t: str, words: List[str]) -> int:
    t2 = (t or "").lower()
    return sum(1 for w in words if w.lower() in t2)

def rules_feat(texts: List[str]):
    rows = []
    for t in texts:
        rows.append([
            int(_hits(t, API_TERMS)   > 0),
            int(_hits(t, POLICY_TERMS)> 0),
            int(_hits(t, ERROR_TERMS) > 0),
            int(_hits(t, PRICE_TERMS) > 0),
            int(_hits(t, PROFILE_TERMS)>0),
        ])
    X = np.asarray(rows, dtype="float64")
    return sparse.csr_matrix(X)
