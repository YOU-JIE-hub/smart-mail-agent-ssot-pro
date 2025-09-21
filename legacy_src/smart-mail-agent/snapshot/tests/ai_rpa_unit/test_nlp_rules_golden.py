from ai_rpa.nlp import analyze_text

def test_rules_golden_default():
    cases = {
        "我要退款，客服幫我": ["refund","support"],
        "想要合作，請提供報價": ["sales","quote"],
    }
    for txt, need in cases.items():
        ints = analyze_text(txt, model="rules:default")["intents"]
        for k in need:
            assert k in ints, f"missing {k} for: {txt} -> {ints}"
