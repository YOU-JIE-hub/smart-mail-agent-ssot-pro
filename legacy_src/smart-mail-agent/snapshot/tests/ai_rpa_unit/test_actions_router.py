from ai_rpa.actions_router import plan_from_categories, plan

def test_plan_from_categories_order_and_dedup():
    cats = ["tech_support","business","tech_support"]
    acts = plan_from_categories(cats)
    assert acts == ["create_support_ticket","reply_support_ack","reply_business","generate_pdf_quote"]

def test_plan_from_intents_old_labels():
    intents = ["refund","quote"]  # 舊詞
    acts = plan(intents)
    # refund -> tech_support, quote -> business
    assert "create_support_ticket" in acts and "generate_pdf_quote" in acts
