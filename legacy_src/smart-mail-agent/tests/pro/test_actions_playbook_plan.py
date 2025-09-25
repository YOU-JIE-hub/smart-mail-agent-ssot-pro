import json
from ai_rpa import actions as actions_mod
from ai_rpa.actions_router import plan, plan_from_categories

def _ids(steps): return [s.get("id") for s in steps]

def test_plan_refund_with_context(monkeypatch):
    # 假裝抓到 H1，確認 context 步驟附加
    scraped = [{"tag":"h1","text":"產品介紹"}]
    steps = plan("我要退款 訂單錯了", scraped)
    ids = _ids(steps)
    assert "collect_order_info" in ids and "policy_check" in ids
    assert ids[-1] == "context"

def test_plan_support_basic():
    steps = plan("需要客服協助")
    ids = _ids(steps)
    assert ids[:2] == ["triage","create_ticket"]

def test_plan_sales_basic():
    steps = plan("想合作 需要方案")
    ids = _ids(steps)
    assert "qualify" in ids and "book_meeting" in ids

def test_plan_quote_basic():
    steps = plan("請提供報價 20 套")
    assert any(s["id"]=="pricing" for s in steps)

def test_plan_invoice_basic():
    steps = plan("發票重開 謝謝")
    assert any(s["id"]=="reissue" for s in steps)

def test_plan_from_categories_general_fallback():
    steps = plan_from_categories(["unknown"])
    assert steps and steps[0]["id"] in ("classify","collect_order_info","triage")

def test_actions_module_write_json(tmp_path):
    path = tmp_path/"out.json"
    actions_mod.write_json({"p": tmp_path}, path)
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d["p"] == str(tmp_path)
