import json, glob, os
REQUIRED = {"quarantine","create_support_ticket","create_quote_ticket",
            "escalate_to_CX","send_policy_docs","update_profile","manual_triage"}
def test_actions_jsonl_schema_and_values():
    cands = sorted(glob.glob("reports_auto/e2e_mail/*")+glob.glob("reports_auto/e2e_run/*"), reverse=True)
    assert cands, "no e2e outputs"
    path = os.path.join(cands[0],"actions.jsonl"); assert os.path.exists(path)
    seen=set()
    for line in open(path,"r",encoding="utf-8"):
        o=json.loads(line); assert "action" in o and o["action"]; seen.add(o["action"])
    assert seen.issubset(REQUIRED), f"unknown actions: {seen-REQUIRED}"
