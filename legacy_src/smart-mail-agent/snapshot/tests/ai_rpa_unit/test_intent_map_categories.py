from ai_rpa.intent_map import to_categories

def test_old_labels_to_canonical():
    assert to_categories(["support","refund"]) == ["tech_support"]
    assert to_categories(["sales","quote","rfq"]) == ["business"]
    assert to_categories(["complaint"]) == ["complaint"]

def test_canonical_passthrough_and_unknown():
    assert to_categories(["policy_query","business"]) == ["policy_query","business"]
    assert to_categories(["random_unknown"]) == ["other"]
