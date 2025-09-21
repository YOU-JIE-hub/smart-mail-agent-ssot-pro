import json
from ai_rpa.actions_router import plan
def _ids(steps): return [s["id"] for s in steps]

def test_tech_support():
    ids = _ids(plan("無法登入 系統錯誤 請協助"))
    assert ids[:2] == ["triage","create_ticket"]

def test_profile_update_diff():
    steps = plan("請將電話從0912-345-678改為0955-123-456，並更新 email 從 a@x.com 到 b@y.com")
    # diff_draft 步驟包含兩筆 replace
    diff = next(s for s in steps if s["id"]=="diff_draft")["params"]["draft"]
    assert len(diff) >= 1 and any(d["path"]=="/phone" for d in diff)

def test_policy_qa_rag():
    ids = _ids(plan("想了解退款機制與使用限制"))
    assert ids[:2] == ["retrieve","compose"]

def test_complaint_flow():
    ids = _ids(plan("真的很失望 處理延遲 一直沒有回覆 這是投訴"))
    assert "auto_apology" in ids and "internal_alert" in ids

def test_biz_quote_flow():
    ids = _ids(plan("想洽談合作，請提供正式方案與報價"))
    assert "prepare_quote" in ids and "generate_pdf" in ids

def test_other_flow():
    ids = _ids(plan("哈囉 測試信"))
    assert "classify" in ids and "no_op" in ids
