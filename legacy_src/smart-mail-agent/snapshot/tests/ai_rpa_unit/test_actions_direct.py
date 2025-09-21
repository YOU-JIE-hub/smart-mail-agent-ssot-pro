from __future__ import annotations
from ai_rpa.actions import plan_actions

def test_support_only():
    assert plan_actions(["support"]) == ["reply_support"]

def test_sales_only():
    assert plan_actions(["sales"]) == ["send_quote"]

def test_both_order_and_dedup():
    # 有重複也只出現一次，且順序固定 support 在前
    acts = plan_actions(["support", "sales", "support"])
    assert acts == ["reply_support", "send_quote"]

def test_unknown_and_empty():
    assert plan_actions(["random", ""]) == []
    assert plan_actions([]) == []
