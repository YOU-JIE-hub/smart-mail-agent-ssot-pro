from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from .intent_map import to_categories
from .actions_playbook import PLAYBOOK

_PHONE_RE = re.compile(r"(09\d{2}[- ]?\d{3}[- ]?\d{3})")
_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")

def _extract_profile_diff(text: str) -> List[Dict[str, str]]:
    diffs: List[Dict[str, str]] = []
    t = text or ""
    m = re.search(r"電話.*?從\s*(" + _PHONE_RE.pattern + r")\s*(?:改為|到)\s*(" + _PHONE_RE.pattern + r")", t)
    if m:
        diffs.append({"op":"replace","path":"/phone","from":m.group(1),"value":m.group(3)})
    m2 = re.search(r"email.*?從\s*(" + _EMAIL_RE.pattern + r")\s*(?:改為|到)\s*(" + _EMAIL_RE.pattern + r")", t, re.IGNORECASE)
    if m2:
        diffs.append({"op":"replace","path":"/email","from":m2.group(1),"value":m2.group(2)})
    return diffs

def _append_context(steps: List[Dict[str, Any]], scraped: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if scraped:
        hints = [it.get("text","") for it in scraped if it.get("tag") in ("h1","p")]
        steps = [*steps, {"id":"context","action":"context.attach","params":{"hints":hints},"desc":"附加網頁上下文"}]
    return steps

def plan(text: str, scraped: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    cats = to_categories(text)
    order = ["policy_qa","profile_update","refund","complaint","invoice","biz_quote","support","other"]
    key = next((c for c in order if c in cats), "other")
    steps = [dict(s) for s in PLAYBOOK[key]]
    if key == "profile_update":
        for i, s in enumerate(steps):
            if s["id"] == "diff_draft":
                draft = _extract_profile_diff(text)
                steps[i] = {**s, "params": {**s.get("params", {}), "draft": draft}}
                break
    return _append_context(steps, scraped)

def plan_from_categories(categories: List[str], scraped: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    if not categories:
        return _append_context([*PLAYBOOK["other"]], scraped)
    for c in categories:
        if c in PLAYBOOK:
            return _append_context([*PLAYBOOK[c]], scraped)
    return _append_context([*PLAYBOOK["other"]], scraped)

def route(text: str, scraped: Optional[List[Dict[str, Any]]] = None, blocked: bool = False) -> List[Dict[str, Any]]:
    if blocked:
        return []
    return plan(text, scraped=scraped)
