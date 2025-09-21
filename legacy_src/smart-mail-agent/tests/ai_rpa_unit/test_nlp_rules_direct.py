from __future__ import annotations
from ai_rpa.nlp import analyze_text

def test_sales_keywords_zh():
    r = analyze_text("想要合作，請提供報價方案")
    assert "sales" in r["intents"]

def test_support_keywords_zh():
    r = analyze_text("發票錯了，想退款")
    assert "support" in r["intents"]

def test_none():
    r = analyze_text("只是打個招呼")
    assert r["intents"] == []
