from smart_mail_agent.ml import infer


def test_intent6_basic():
    assert infer.predict_intent("請提供報價與折扣")["intent"] == "quote"
    assert infer.predict_intent("PO-1234 下單")["intent"] in ("order", "quote")
