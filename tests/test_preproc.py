import os, inspect, pytest
from runtime_preproc import normalize_text

sig = inspect.signature(normalize_text)
if "task" not in sig.parameters:
    pytest.skip("normalize_text not task-aware; skipping URL policy tests", allow_module_level=True)

def test_intent_url_drop_policy(monkeypatch):
    monkeypatch.setenv("INTENT_URL_POLICY", "drop")
    s = "我要投訴 http://x.example/a"
    got = normalize_text(s, task="intent")
    assert "http" not in got and "<URL>" not in got

def test_spam_tokenize_policy():
    s = "FREE $$$ http://spam"
    got = normalize_text(s, task="spam")
    assert "<URL>" in got
