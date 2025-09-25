from __future__ import annotations
from typing import Iterable, List

# 對外唯一標準（6 類）
CANONICAL = [
    "tech_support",   # 技術支援/退款等客服請求
    "profile_update", # 帳戶/資料異動
    "policy_query",   # 問流程/規則/FAQ
    "complaint",      # 投訴與抱怨
    "business",       # 業務/合作/報價
    "other",          # 其他
]

# 舊意圖/同義詞 → 6 類
OLD_TO_CANON = {
    # 支援/退款
    "support": "tech_support",
    "refund": "tech_support",
    "ticket": "tech_support",
    # 資料異動
    "profile_update": "profile_update",
    "update_profile": "profile_update",
    "data_change": "profile_update",
    # 規則/FAQ
    "policy": "policy_query",
    "policy_query": "policy_query",
    "faq": "policy_query",
    "regulation": "policy_query",
    # 投訴
    "complaint": "complaint",
    "apology": "complaint",
    # 業務/報價
    "sales": "business",
    "quote": "business",
    "rfq": "business",
    "business": "business",
}

def to_categories(intents: Iterable[str] | None) -> List[str]:
    """把任意舊/新意圖映射到 6 類；未知→other；順序穩定去重。"""
    seen, out = set(), []
    for raw in intents or []:
        key = str(raw).strip().lower()
        cat = OLD_TO_CANON.get(key)
        if cat is None:
            cat = key if key in CANONICAL else "other"
        if cat not in seen:
            seen.add(cat)
            out.append(cat)
    return out
