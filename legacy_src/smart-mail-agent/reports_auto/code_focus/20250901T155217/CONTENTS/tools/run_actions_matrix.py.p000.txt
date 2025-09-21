#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "output" / "matrix"
OUT_DIR.mkdir(parents=True, exist_ok=True)
out = OUT_DIR / "matrix_summary.json"


def case(i: int, action: str, subject: str) -> dict:
    base = {
        "id": f"sample-{i}",
        "action": action,
        "spam": False,
        "request": {
            "subject": subject,
            "from": "test@example.com",
            "body": "hi",
            "attachments": [],
        },
        "expected": {"action": action, "spam": False},
        "result": {"action": action, "spam": False},
        "meta": {"source": "stub"},
    }
    return base


cases = [
    case(0, "reply_general", "hello"),
    case(1, "reply_faq", "faq about pricing"),
    case(2, "reply_support", "need help"),
    case(3, "apply_info_change", "please update my info"),
    case(4, "sales", "interested in plan"),
]

payload = {
    "version": 1,
    "generated_at": os.environ.get("GITHUB_SHA") or "local",
    "total_cases": len(cases),
    "cases": cases,
    "buckets": [],
}

out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[matrix] wrote {out}")
