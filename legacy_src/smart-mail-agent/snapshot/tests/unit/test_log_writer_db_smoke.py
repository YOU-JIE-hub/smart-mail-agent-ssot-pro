from __future__ import annotations

import sqlite3
from pathlib import Path

from smart_mail_agent.observability.log_writer import log_to_db


def test_log_to_db_inserts_row(tmp_path: Path):
    db = tmp_path / "emails_log.db"
    rid1 = log_to_db(
        subject="S1",
        content="C1",
        summary="Sum1",
        predicted_label="reply_faq",
        confidence=0.9,
        action="auto_reply",
        error="",
        db_path=db,
    )
    rid2 = log_to_db(subject="S2", db_path=db)
    assert isinstance(rid1, int) and isinstance(rid2, int) and rid2 >= rid1
    con = sqlite3.connect(str(db))
    try:
        (cnt,) = con.execute("SELECT COUNT(*) FROM emails_log").fetchone()
        assert cnt >= 2
        row = con.execute(
            "SELECT subject, predicted_label, action FROM emails_log ORDER BY id ASC LIMIT 1"
        ).fetchone()
        assert row[0] == "S1" and row[1] == "reply_faq" and row[2] == "auto_reply"
    finally:
        con.close()
