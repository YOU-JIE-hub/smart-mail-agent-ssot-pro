from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict


def extract_fields(text: str) -> Dict[str, str]:
    text = text or ""
    m_phone = re.search(r"(09\d{2}[-]?\d{3}[-]?\d{3})", text)
    m_addr = re.search(r"(台北[^\\n\\r]+)", text)
    phone = m_phone.group(1).replace(" ", "") if m_phone else ""
    addr = m_addr.group(1).strip() if m_addr else ""
    return {"phone": phone, "address": addr}


def update_user_info(user: str, text: str, *, db_path: str = ":memory:") -> Dict[str, Any]:
    f = extract_fields(text)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS user_info(email TEXT PRIMARY KEY, phone TEXT, address TEXT)"
    )
    cur.execute("SELECT phone, address FROM user_info WHERE email=?", (user,))
    row = cur.fetchone()
    if row and row[0] == f["phone"] and row[1] == f["address"]:
        conn.close()
        return {"status": "no_change"}
    cur.execute(
        "INSERT OR REPLACE INTO user_info(email, phone, address) VALUES(?,?,?)",
        (user, f["phone"], f["address"]),
    )
    conn.commit()
    conn.close()
    return {"status": "updated"}
