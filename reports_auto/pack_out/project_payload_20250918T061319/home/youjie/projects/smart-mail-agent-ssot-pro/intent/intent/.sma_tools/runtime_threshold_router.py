# -*- coding: utf-8 -*-
import re
LABELS = ["biz_quote","complaint","other","policy_qa","profile_update","tech_support"]
_RULES = [
    ("biz_quote", [
        r"報價", r"詢價", r"報個\s*quote", r"\bquote\b",
        r"報.*?金額", r"請開.*?報價", r"報(?!告).*?(?:單|價格|金額)"
    ]),
    ("tech_support", [
        r"壞了", r"故障", r"無法(啟動|登入|使用)", r"連不上",
        r"維修|RMA", r"請.*?協助", r"技術(支援|問題)"
    ]),
    ("complaint", [
        r"抱怨|投訴|客訴", r"太慢", r"不滿意", r"沒回覆", r"延遲", r"品質.*?問題"
    ]),
    ("profile_update", [
        r"更新(資料|資訊|地址|電話|抬頭)", r"變更(聯絡|公司|抬頭|地址|電話)", r"修改(資料|資訊)"
    ]),
    ("policy_qa", [
        r"保固|保修|維修條款", r"退換貨|退貨|換貨", r"\bSLA\b|服務水準", r"付款方式", r"開發票|發票|發票抬頭"
    ]),
]
def predict_one(text:str)->str:
    t = text.strip()
    for label, pats in _RULES:
        for p in pats:
            if re.search(p, t, flags=re.IGNORECASE):
                return label
    return "other"
def predict(texts):
    return [predict_one(x) for x in texts]
