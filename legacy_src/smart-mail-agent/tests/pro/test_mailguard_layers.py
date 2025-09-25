from ai_rpa.mailguard import detect, load_default_ruleset
import ai_rpa.spam_adapter as spam_adapter
import types

def test_mailguard_block_by_header():
    hd = {"X-Spam-Flag":"YES"}
    out = detect("hello", headers=hd)
    assert out["verdict"]=="BLOCK" and any("X-Spam-Flag: YES" in r for r in out["reasons"])

def test_mailguard_block_by_adapter(monkeypatch):
    # 模型回高分 spam
    monkeypatch.setattr(spam_adapter, "score", lambda texts: {"label":"spam","score":0.95})
    out = detect("regular text")
    assert out["verdict"]=="BLOCK" and "adapter_high_score" in out["reasons"]

def test_mailguard_allow_low_score(monkeypatch):
    monkeypatch.setattr(spam_adapter, "score", lambda texts: {"label":"ham","score":0.05})
    out = detect("hello world")
    assert out["verdict"]=="ALLOW"

def test_ruleset_export():
    r = load_default_ruleset()
    assert "adapter_block" in r and r["adapter_block"] >= 0.5
