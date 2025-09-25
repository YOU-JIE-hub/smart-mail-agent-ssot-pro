from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from smart_mail_agent.utils.config import paths


def _rules_path() -> Path:
    return paths().root / "policies" / "rules.yaml"


def load_rules() -> dict[str, Any]:
    p = _rules_path()
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def apply_policies(ctx: dict[str, Any]) -> dict[str, Any]:
    """
    ctx: {mail, intent, kie{fields}, intent_score}
    returns: {alerts:[], tickets:[], changes:[]}
    """
    rules = load_rules()
    out: dict[str, list] = {"alerts": [], "tickets": [], "changes": []}
    intent = ctx.get("intent")
    f = (ctx.get("kie") or {}).get("fields") or {}

    # 範例規則：高金額報價 -> 產生 alert
    if intent == "quote":
        try:
            thr = float((rules.get("quote") or {}).get("high_amount", 0))
        except Exception:
            thr = 0.0
        try:
            amt = float((f.get("amount") or "0").replace(",", ""))
            if amt >= thr:
                out["alerts"].append(
                    {
                        "level": (rules.get("quote") or {}).get("alert_level", "high"),
                        "message": f"High deal amount {amt} >= {thr}",
                    }
                )
        except Exception:
            pass

    # 範例：物流缺 tracking -> ticket
    if intent == "logistics" and not f.get("tracking_no"):
        out["tickets"].append({"type": "need_tracking"})

    # 範例：保固 -> 開 RMA
    if intent == "warranty":
        out["tickets"].append({"type": "rma_open"})

    return out
