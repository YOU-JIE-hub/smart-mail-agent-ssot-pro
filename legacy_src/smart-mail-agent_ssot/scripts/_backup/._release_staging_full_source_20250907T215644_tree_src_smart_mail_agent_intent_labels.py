#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/intent/labels.py
# 模組用途
#   意圖標籤對齊與規則化。
from __future__ import annotations

CANON = ("biz_quote", "tech_support", "complaint", "policy_qa", "profile_update", "other")

RULES: dict[str, str] = {
    "sales_quote": "biz_quote",
    "quote": "biz_quote",
    "support": "tech_support",
    "faq": "policy_qa",
}


def to_canonical(raw: str) -> str:
    """參數: 原始標籤；回傳: 規範化標籤。"""
    x = (raw or "").strip().lower().replace(" ", "_")
    if x in CANON:
        return x
    if x in RULES:
        return RULES[x]
    for key, cat in RULES.items():
        if key in x:
            return cat
    return "other"
