from __future__ import annotations
from typing import Iterable, List
from .intent_map import to_categories

__all__ = ["plan_from_categories", "plan"]

def plan_from_categories(categories: Iterable[str] | None) -> List[str]:
    """輸入 6 類，輸出穩定順序的動作清單（無副作用）。"""
    cats = [str(c or "").strip().lower() for c in (categories or [])]
    seen, acts = set(), []
    def add(x: str):
        if x not in seen:
            seen.add(x); acts.append(x)

    if "tech_support" in cats:
        add("create_support_ticket")
        add("reply_support_ack")

    if "profile_update" in cats:
        add("generate_update_draft")
        add("reply_update_confirmation")

    if "policy_query" in cats:
        add("rag_answer")
        add("reply_policy")

    if "complaint" in cats:
        add("send_apology")
        add("escalate_alert")

    if "business" in cats:
        add("reply_business")
        add("generate_pdf_quote")

    # other：不做動作
    return acts

def plan(intents: Iterable[str] | None) -> List[str]:
    """舊/新意圖皆可進來，會先映射到 6 類再規劃。"""
    return plan_from_categories(to_categories(intents or []))
