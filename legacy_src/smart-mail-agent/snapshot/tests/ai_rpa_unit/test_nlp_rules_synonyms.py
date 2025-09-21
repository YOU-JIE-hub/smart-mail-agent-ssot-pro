from __future__ import annotations
from ai_rpa.nlp import analyze_text

def test_rules_default_synonyms_en():
    cases = {
        "Please issue a refund": ["refund"],
        "I'm returning the item": ["refund"],
        "Need pricing / quotation": ["sales","quote"],
        "RFQ for your product": ["sales","quote"],
    }
    for txt, need in cases.items():
        ints = analyze_text(txt, model="rules:default")["intents"]
        for k in need:
            assert k in ints, f"missing {k} for: {txt} -> {ints}"
