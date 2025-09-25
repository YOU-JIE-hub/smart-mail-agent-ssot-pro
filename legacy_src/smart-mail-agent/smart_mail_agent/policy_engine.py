from __future__ import annotations
MAP = {
    "biz_quote": "create_quote_ticket",
    "tech_support": "create_support_ticket",
    "complaint": "escalate_to_CX",
    "policy_qa": "send_policy_docs",
    "profile_update": "update_profile",
    "other": "manual_triage",
}
def decide(label: str) -> str:
    return MAP.get(label, "manual_triage")
