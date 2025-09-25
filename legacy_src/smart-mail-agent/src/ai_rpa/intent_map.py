from __future__ import annotations
from typing import List

def _has_any(s: str, kws: list[str]) -> bool:
    s2 = s.lower()
    return any(k.lower() in s2 for k in kws)

def to_categories(text: str) -> List[str]:
    t = text or ""
    zht = text or ""

    # 規則/流程詢問（優先）
    if _has_any(t, ["流程","規則","條件","機制","使用限制","faq","policy","how to"]):
        return ["policy_qa"]

    # 技術支援/客服協助
    if _has_any(t, [
        "無法登入","系統錯誤","error","exception","故障","當機","操作異常","bug",
        "需要客服協助","客服協助","客服","協助","支援","support","幫忙"
    ]):
        return ["support"]

    # 發票
    if _has_any(t, ["發票重開","發票","invoice","re-issue"]):
        return ["invoice"]

    # 退款/退費
    if _has_any(t, ["refund","退貨","退款","退費"]):
        return ["refund"]

    # 投訴
    if _has_any(t, ["抱怨","投訴","不滿","失望","延遲"]):
        return ["complaint"]

    # 業務/報價
    if _has_any(t, ["合作","洽談","報價","方案"]):
        return ["biz_quote"]

    # 資料異動
    if _has_any(t, ["更新","修改","變更","改為","重設","更名","地址","電話"]) or "更新 email" in zht:
        return ["profile_update"]

    return ["other"]
