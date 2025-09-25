from __future__ import annotations

# -*- coding: utf-8 -*-
import importlib
from typing import Any

_ALIASES = {
    "business_inquiry": "sales_inquiry",
    "sales": "sales_inquiry",
    "complain": "complaint",
}


def _normalize(label: str) -> str:
    return _ALIASES.get(label, label)


def _get_orig():
    mod = importlib.import_module("action_handler")
    return getattr(mod, "_orig_handle", None)


def handle(req: dict[str, Any]) -> dict[str, Any]:
    label = (req.get("predicted_label") or "").strip().lower()
    label = _normalize(label)
    req["predicted_label"] = label

    if label == "sales_inquiry":
        return importlib.import_module("actions.sales_inquiry").handle(req)
    if label == "complaint":
        return importlib.import_module("actions.complaint").handle(req)

    orig = _get_orig()
    if callable(orig):
        return orig(req)
    return {"ok": True, "action": "reply_general", "subject": "[自動回覆] 一般諮詢"}
