import os, sys, types, importlib

def test_spam_adapter_ml_and_rule(monkeypatch):
    import ai_rpa.spam_adapter as sa
    # 規則分支
    monkeypatch.delenv("SMA_SPAM_BACKEND", raising=False)
    importlib.reload(sa)
    r_rule = sa.score("FREE money right now")
    assert isinstance(r_rule, dict) and r_rule["score"] >= 1.0

    # ML 分支（以 stub 模組注入）
    monkeypatch.setenv("SMA_SPAM_BACKEND", "ml")
    sml = types.ModuleType("models.spam.serving_ml")
    sml.available = lambda: True
    sml.score_prob_spam = lambda text: 0.42
    sys.modules["models.spam"] = types.ModuleType("models.spam")
    sys.modules["models.spam.serving_ml"] = sml
    importlib.reload(sa)
    r_ml = sa.score(["hello","world"])
    assert 0.41 < r_ml["score"] < 0.43 and "ml_prob" in r_ml.get("reasons", [])

def test_nlp_ml_branch(monkeypatch):
    import ai_rpa.nlp as nlp
    monkeypatch.setenv("SMA_INTENT_BACKEND", "ml")
    iml = types.ModuleType("models.intent.serving_ml")
    iml.available = lambda: True
    iml.predict = lambda text: {"intents": ["sales"], "labels": ["biz_quote"], "length": len(text.split())}
    sys.modules["models.intent"] = types.ModuleType("models.intent")
    sys.modules["models.intent.serving_ml"] = iml
    importlib.reload(nlp)
    out = nlp.analyze_text("合作 報價")
    assert "sales" in out["intents"] and "summary" in out
