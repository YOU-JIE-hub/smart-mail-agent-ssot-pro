from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from .common import pipeline_log
from .types import ActionContext


def create_ticket(ctx: ActionContext, mail_id: str, title: str, severity: str, key: str, extra: dict[str, Any]) -> int:
    with sqlite3.connect(ctx.db_path) as conn:
        ts = int(time.time())
        conn.execute(
            "INSERT OR IGNORE INTO tickets(ts,mail_id,title,severity,status,extra,idempotency_key) VALUES(?,?,?,?,?,?,?)",
            (ts, mail_id, title, severity, "open", json.dumps(extra, ensure_ascii=False), key),
        )
        conn.commit()
    pipeline_log(ctx, {"stage": "action/ticket_create", "level": "info", "mail_id": mail_id, "idempotency_key": key})
    return 0
