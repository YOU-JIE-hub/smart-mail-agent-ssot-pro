from __future__ import annotations
from tools.ml_io import predict as _ml_predict
try:
    import sma_features as F
except Exception:
    from src import sma_features as F  # 規則特徵
# 你的 IDX2NAME 如需客製可從外部載；先以簡化範例示意
IDX2NAME = {
    0:"報價",1:"投訴",2:"一般回覆",3:"規則詢問",4:"資料異動",5:"技術支援",
}
KEY2IDX = {"報價":0,"投訴":1,"一般回覆":2,"規則詢問":3,"資料異動":4,"技術支援":5}

def _rule_hint(email:dict)->dict:
    # 從你規則特徵/或簡單關鍵字，取強訊號（示意）
    subj=(email.get("subject") or "") + " " + (email.get("body") or "")
    hits={}
    for k in KEY2IDX:
        if k in subj: hits[k]=1.0
    return hits

def classify_boosted(email:dict)->dict:
    """規則優先：有強訊號直接採用；否則退回 ML。回傳 dict：{intent, confidence, slots}"""
    hints=_rule_hint(email)
    if hints:
        # 取第一個命中（你可以改為更精細的分數邏輯）
        intent=next(iter(hints.keys()))
        return {"intent":intent,"confidence":0.88,"slots":{}}
    # 退回 ML
    r=_ml_predict(email)
    intent = r.get("intent_name") or r.get("intent") or r.get("label") or ""
    conf   = float(r.get("confidence",1.0))
    return {"intent":intent,"confidence":conf,"slots":{}}


def classify_ml_boosted(email):
    return classify_boosted(email)
