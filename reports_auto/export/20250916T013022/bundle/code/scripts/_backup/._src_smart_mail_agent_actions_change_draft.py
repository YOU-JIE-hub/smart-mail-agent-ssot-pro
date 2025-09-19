from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


def json_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = set(before) | set(after)
    diff: dict[str, Any] = {"add": {}, "remove": {}, "modify": {}}
    for k in keys:
        if k not in before:
            diff["add"][k] = after[k]
        elif k not in after:
            diff["remove"][k] = before[k]
        elif before[k] != after[k]:
            diff["modify"][k] = {"from": before[k], "to": after[k]}
    return diff


def persist_change(
    db_path: str,
    mail_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    diff: dict[str, Any],
    key: str,
) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS changes(
                   id INTEGER PRIMARY KEY,
                   idem TEXT,
                   data TEXT,
                   created_at TEXT DEFAULT (datetime('now'))
               )"""
        )
        payload = {
            "mail_id": mail_id,
            "before": before,
            "after": after,
            "diff": diff,
            "ts": int(time.time()),
        }
        conn.execute(
            "INSERT OR IGNORE INTO changes(idem, data) VALUES(?, ?)",
            (key, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
