from smart_mail_agent.actions.router import route
from smart_mail_agent.policy.engine import apply_policies


def test_policy_and_route_smoke():
    mail = {"id": "X1", "body": "報價 金額 NT$60,000"}
    kie = {"fields": {"amount": "60,000"}}
    pol = apply_policies({"mail": mail, "intent": "quote", "kie": kie, "intent_score": 0.9})
    act = route(mail, "quote", kie)
    assert "alerts" in pol and "artifacts" in act
