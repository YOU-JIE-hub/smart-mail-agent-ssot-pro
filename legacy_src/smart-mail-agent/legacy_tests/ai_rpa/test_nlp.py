from ai_rpa.nlp import analyze_text


def test_analyze_text_offline():
    out = analyze_text(["我要退款", "想合作直播"], model="offline-keyword")
    assert out["labels"] == ["refund", "sales"]
