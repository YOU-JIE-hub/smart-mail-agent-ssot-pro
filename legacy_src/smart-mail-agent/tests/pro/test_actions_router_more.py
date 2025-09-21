from ai_rpa.actions_router import plan, route

def test_plan_refund_adds_context_when_scraped():
    steps = plan("我要退款 訂單錯了", scraped=[{"tag":"h1","text":"產品介紹"}])
    assert steps and steps[-1]["id"] == "context"

def test_route_blocked_returns_empty_steps():
    out = route("單純測試", scraped=None, blocked=True)
    assert isinstance(out, list) and out == []
