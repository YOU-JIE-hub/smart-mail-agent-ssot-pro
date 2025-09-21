from smart_mail_agent.ml import infer


def test_ml_schemas():
    s = infer.predict_spam("免費優惠")
    i = infer.predict_intent("我要報價與付款方式")
    assert "label" in s and "intent" in i
