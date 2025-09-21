from ai_rpa.mailguard import detect, load_default_ruleset
from ai_rpa import spam_adapter
import types

def test_header_flag_blocks():
    out = detect("hello", headers={"X-Spam-Flag":"YES"})
    assert out["verdict"] == "BLOCK"
    assert any("X-Spam-Flag: YES" in r for r in out["reasons"])
    assert out["layers"]["header"] >= 1.0

def test_adapter_high_score_blocks(monkeypatch):
    monkeypatch.setattr(spam_adapter, "score", lambda texts: {"label":"spam","score":0.95})
    out = detect("ordinary text")
    assert out["verdict"] in ("WARN","BLOCK")
    assert "adapter_high_score" in out["reasons"]
    assert out["layers"]["adapter"] >= 0.6

def test_ruleset_export_contains_adapter_block():
    rules = load_default_ruleset()
    assert "adapter_block" in rules["thresholds"] and rules["thresholds"]["adapter_block"] >= 0.5
