#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/observability/audit.py
# 模組用途
#   SQLite 與 NDJSON 審計。
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs     (ts INTEGER PRIMARY KEY, note TEXT);
CREATE TABLE IF NOT EXISTS mails    (mail_id TEXT PRIMARY KEY, subject TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS intents  (mail_id TEXT, intent TEXT, p REAL, ts INTEGER);
CREATE TABLE IF NOT EXISTS actions  (mail_id TEXT, action TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS errors   (ts INTEGER, message TEXT);
"""


class Audit:
    def __init__(self, project_root: Path):
        self.root = Path(project_root)
        self.db = self.root / "db" / "sma.sqlite"
        self.nd = self.root / "reports_auto" / "logs" / "pipeline.ndjson"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.nd.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.db)
        con.executescript(SCHEMA)
        con.commit()
        con.close()

    def log(self, stage: str, level: str, meta: dict[str, Any]) -> None:
        rec = {"ts": int(time.time()), "stage": stage, "level": level, **meta}
        with self.nd.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        try:
            con = sqlite3.connect(self.db)
            cur = con.cursor()
            if stage == "ingest" and "mail_id" in meta:
                cur.execute(
                    "INSERT OR IGNORE INTO mails(mail_id,subject,ts) VALUES(?,?,?)",
                    (meta.get("mail_id"), meta.get("subject", ""), rec["ts"]),
                )
            if stage == "intent" and "mail_id" in meta:
                cur.execute(
                    "INSERT INTO intents(mail_id,intent,p,ts) VALUES(?,?,?,?)",
                    (meta.get("mail_id"), meta.get("intent"), float(meta.get("p", 0.0)), rec["ts"]),
                )
            if stage == "action" and "mail_id" in meta:
                cur.execute(
                    "INSERT INTO actions(mail_id,action,ts) VALUES(?,?,?)",
                    (meta.get("mail_id"), meta.get("action"), rec["ts"]),
                )
            con.commit()
        except Exception:
            pass
        finally:
            try:
                con.close()  # type: ignore[has-type]
            except Exception:
                pass
