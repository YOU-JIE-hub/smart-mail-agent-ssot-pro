from ai_rpa.actions_router import plan

def test_profile_update_diff_both_phone_and_email():
    text = "請將電話從0912-345-678改為0955-123-456，並將email從 a@x.com 改為 c@z.com"
    steps = plan(text)
    diff = next(s for s in steps if s["id"]=="diff_draft")["params"]["draft"]
    paths = {d["path"] for d in diff}
    assert "/phone" in paths and "/email" in paths
