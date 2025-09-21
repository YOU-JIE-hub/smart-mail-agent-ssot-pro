from __future__ import annotations

import json
import time
import uuid
from datetime import datetime

from .config import paths
from .redact import redact_text


def log_jsonln(rel_name: str, obj: dict, *, redact: bool = False) -> None:
    p = paths()
    fp = p.logs / rel_name
    fp.parent.mkdir(parents=True, exist_ok=True)
    base = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "corr_id": obj.get("corr_id") or str(uuid.uuid4()),
    }
    item = {**base, **(obj or {})}
    if redact and "body" in item:
        item["body"] = redact_text(item["body"])
    with fp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def time_ms() -> int:
    return int(time.time() * 1000)
