from ai_rpa.nlp import analyze_text


def test_analyze_text_fallback_to_offline():
    out = analyze_text(["我要退款"], model="transformers")
    # 會經過 warning 分支後回到 offline-keyword
    assert out["labels"] == ["refund"]
