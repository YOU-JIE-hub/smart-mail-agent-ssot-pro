from ai_rpa.actions_router import plan_from_categories

def test_plan_from_categories_general_fallback_with_context():
    steps = plan_from_categories(["unknown"], scraped=[{"tag":"p","text":"這是一段介紹文字"}])
    assert steps and steps[0]["id"] in ("classify","summarize")
    assert steps[-1]["id"] == "context"
