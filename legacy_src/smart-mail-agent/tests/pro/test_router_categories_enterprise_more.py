from ai_rpa.actions_router import plan

def _ids(steps): return [s["id"] for s in steps]

def test_support_flow():
    ids = _ids(plan("無法登入 需要技術支援"))
    assert "triage" in ids and "create_ticket" in ids

def test_profile_update_flow():
    ids = _ids(plan("請把電話從0912-345-678改為0955-123-456，變更地址成台北市"))
    assert "diff_draft" in ids

def test_policy_qa_flow():
    ids = _ids(plan("想了解退款機制與使用限制"))
    assert "retrieve" in ids and "compose" in ids

def test_complaint_flow():
    ids = _ids(plan("真的很失望，處理延遲，這是投訴"))
    assert "auto_apology" in ids and "internal_alert" in ids

def test_biz_quote_flow():
    ids = _ids(plan("想洽談合作，請提供正式方案與報價"))
    assert "pricing" in ids and "generate_pdf" in ids and "send_email" in ids

def test_other_flow():
    ids = _ids(plan("哈囉 測試信"))
    assert "classify" in ids and "summarize" in ids
