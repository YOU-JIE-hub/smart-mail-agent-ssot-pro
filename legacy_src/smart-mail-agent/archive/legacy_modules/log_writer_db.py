from __future__ import annotations

import datetime
import pathlib
import sqlite3


def log_to_db(
    *,
    subject: str,
    content: str,
    summary: str,
    predicted_label: str,
    confidence: float,
    action: str,
    error: str,
    db_path: str | pathlib.Path,
) -> int:
    p = pathlib.Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS emails_log(
            id INTEGER PRIMARY KEY,
            subject TEXT, content TEXT, summary TEXT,
            predicted_label TEXT, confidence REAL,
            action TEXT, error TEXT, ts TEXT
        )"""
        )
        cur = c.execute(
            """INSERT INTO emails_log(subject,content,summary,predicted_label,confidence,action,error,ts)
                           VALUES(?,?,?,?,?,?,?,?)""",
            (
                subject,
                content,
                summary,
                predicted_label,
                float(confidence),
                action,
                error,
                datetime.datetime.utcnow().isoformat(),
            ),
        )
        return int(cur.lastrowid)
