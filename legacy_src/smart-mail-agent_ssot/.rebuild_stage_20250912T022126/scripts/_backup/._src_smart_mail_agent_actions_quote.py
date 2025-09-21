from __future__ import annotations

import json
from typing import Any

from smart_mail_agent.utils.config import paths


def build_quote(mail: dict[str, Any], kie: dict[str, Any]) -> dict[str, Any]:
    order_id = mail.get("id", "ORDER")
    amount = float(kie.get("amount", 0) or 0)
    terms = "收貨後7日內付款；匯款/信用卡/對公轉帳皆可。"
    quote = {
        "order_id": order_id,
        "currency": "TWD",
        "amount": amount,
        "payment_terms": terms,
        "lead_time_days": 5,
        "note": "本報價為示意用；如需正式版本請回信確認。",
    }
    p = paths()
    out = p.status / f"quote_{order_id}.json"
    out.write_text(json.dumps(quote, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "quote_path": str(out), "quote": quote}
