#!/usr/bin/env python3
# 檔案位置: src/smart_mail_agent/observability/audit_db.py
# 模組用途: 集中管理 SQLite 資料表建置與錯誤寫入。

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

DEFAULT_DB = "reports_auto/audit.sqlite3"
SCHEMA = """
CREATE TABLE IF NOT EXISTS err_log  (ts INTEGER, stage TEXT, level TEXT, detail TEXT);
"""


def ensure_db(path: str | None = None) -> Path:
    """
    參數: path: 自訂 DB 路徑
    回傳: Path: 實際 DB 路徑
    """
    db = Path(path or DEFAULT_DB)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.commit()
    con.close()
    return db


def write_err(stage: str, level: str, detail: dict[str, Any], db_path: str | None = None) -> None:
    """
    參數: stage/level/detail/db_path
    回傳: None
    """
    p = ensure_db(db_path)
    con = sqlite3.connect(p)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO err_log(ts,stage,level,detail) VALUES(?,?,?,?)",
        (int(time.time()), stage, level, json.dumps(detail, ensure_ascii=False)),
    )
    con.commit()
    con.close()
