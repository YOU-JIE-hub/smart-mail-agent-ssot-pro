from __future__ import annotations

import datetime
import re
import sqlite3
from typing import Any, Dict


def _parse(content: str) -> Dict[str, str]:
    # 簡單擷取「電話/地址」
    phone = ""
    addr = ""
    if content:
        m = re.search(r"(?:電話|手機)\s*[:：]\s*([0-9\-+ ]{6,})", content)
        if m:
            phone = m.group(1).strip()
        m2 = re.search(r"(?:地址)\s*[:：]\s*(.+)", content)
        if m2:
            addr = m2.group(1).strip()
    return {"phone": phone, "address": addr}


def _ensure_tables(db_path: str) -> None:
    with sqlite3.connect(db_path) as c:
        c.executescript(
            """
        CREATE TABLE IF NOT EXISTS users(
          email TEXT PRIMARY KEY, phone TEXT, address TEXT
        );
        CREATE TABLE IF NOT EXISTS diff_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT, 欄位 TEXT, 原值 TEXT, 新值 TEXT, created_at TEXT
        );
        """
        )


def update_user_info(email: str, content: str, *, db_path: str) -> Dict[str, Any]:
    _ensure_tables(db_path)
    info = _parse(content or "")
    with sqlite3.connect(db_path) as c:
        cur = c.execute("SELECT phone,address FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        if not row:
            return {"status": "not_found"}
        old_phone, old_addr = row
        changes = {}
        if info["phone"] and info["phone"] != (old_phone or ""):
            changes["phone"] = (old_phone or "", info["phone"])
        if info["address"] and info["address"] != (old_addr or ""):
            changes["address"] = (old_addr or "", info["address"])
        if not changes:
            return {"status": "no_change"}
        for field, (ov, nv) in changes.items():
            c.execute(f"UPDATE users SET {field}=? WHERE email=?", (nv, email))
            c.execute(
                "INSERT INTO diff_log(email,欄位,原值,新值,created_at) VALUES(?,?,?,?,?)",
                (email, field, ov, nv, datetime.datetime.utcnow().isoformat()),
            )
        return {"status": "updated", "changes": list(changes.keys())}
