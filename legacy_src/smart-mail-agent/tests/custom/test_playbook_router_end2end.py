import json
from ai_rpa.actions_router import plan

def _ids(steps): return [s["id"] for s in steps]

def test_support_flow():
    ids = _ids(plan("需要客服協助"))
    assert ids[:2] == ["triage","create_ticket"]

def test_refund_flow():
    ids = _ids(plan("想退款 訂單號 123"))
    assert "collect_order_info" in ids and "propose_refund" in ids

def test_sales_flow():
    ids = _ids(plan("想合作 需要方案"))
    assert "qualify" in ids and "book_meeting" in ids

def test_quote_flow():
    ids = _ids(plan("請提供報價 20 套"))
    assert "pricing" in ids and "approval" in ids

def test_invoice_flow():
    ids = _ids(plan("發票重開 謝謝"))
    assert "reissue" in ids

def test_general_flow():
    ids = _ids(plan("隨意打招呼 沒特別需求"))
    assert "classify" in ids and "summarize" in ids
