from ai_rpa.actions_router import route

def test_route_blocked_true():
    out = route({"intents":["support"],"labels":["support"]}, scraped=None, blocked=True)
    assert out == []
