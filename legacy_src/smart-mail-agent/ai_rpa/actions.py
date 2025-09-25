from __future__ import annotations
import os, json, hashlib
from typing import Any, Dict, List
from . import intent_map
from smart_mail_agent.sma_types import normalize_result
from ai_rpa.nlp import analyze_text

__all__ = ["plan_actions","write_json"]

def _idem_key(obj: Any) -> str:
    s = json.dumps(normalize_result(obj), ensure_ascii=False, sort_keys=True).encode("utf-8", "ignore")
    return hashlib.sha1(s).hexdigest()

def plan_actions(text: str, nlp_result: Dict[str,Any] | None = None) -> List[Dict[str,Any]]:
    nlp_result = nlp_result or analyze_text(text)
    cats = intent_map.to_categories(" ".join(nlp_result.get("hits", [])))
    acts: List[Dict[str,Any]] = []
    chosen = cats[0] if cats else "other"
    mapping = {
        "biz_quote": "create_quote_ticket",
        "tech_support": "create_support_ticket",
        "complaint": "escalate_to_CX",
        "policy_qa": "send_policy_docs",
        "profile_update": "update_profile",
        "other": "manual_triage",
    }
    action = mapping.get(chosen, "manual_triage")
    payload = {
        "id": "demo",
        "action": action,
        "fields": {},
    }
    payload["idempotency_key"] = _idem_key(payload)
    acts.append(payload)
    return acts

def write_json(obj: Any, path: str, *, dry_run: bool = False) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = normalize_result(obj)
    if not dry_run:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return path
