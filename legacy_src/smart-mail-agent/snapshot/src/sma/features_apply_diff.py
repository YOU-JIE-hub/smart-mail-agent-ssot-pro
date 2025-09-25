from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

_DB_DEFAULT = {"users": {}}


def _load(db_path: str) -> Dict[str, Any]:
    p = Path(db_path)
    if not p.exists():
        return dict(_DB_DEFAULT)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return dict(_DB_DEFAULT)


def _save(db_path: str, db: Dict[str, Any]) -> None:
    Path(db_path).write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse(text: str) -> Dict[str, str]:
    phone = None
    m = re.search(r"(?:電話|手機)\s*[:：]?\s*([0-9\-+()\s]{3,})", text or "", flags=re.I)
    if m:
        phone = re.sub(r"\D+", "", m.group(1))
    addr = None
    m2 = re.search(r"(?:地址)\s*[:：]?\s*([^\n\r]+)", text or "")
    if m2:
        addr = m2.group(1).strip()
    out: Dict[str, str] = {}
    if phone:
        out["phone"] = phone
    if addr:
        out["address"] = addr
    return out


def _init_db(db_path: str) -> None:
    # 測試會呼叫：建立一筆固定 baseline，email -> phone=0911, address=A路1號
    db = dict(_DB_DEFAULT)
    db["users"]["a@x"] = {"phone": "0911", "address": "A路1號"}
    _save(db_path, db)


def update_user_info(email: str, free_text: str, *, db_path: str) -> Dict[str, Any]:
    db = _load(db_path)
    users: Dict[str, Any] = db.setdefault("users", {})
    old = dict(users.get(email, {}))
    new = _parse(free_text)
    changes: Dict[str, Any] = {}
    merged = dict(old)
    for k, v in new.items():
        if old.get(k) != v:
            changes[k] = {"old": old.get(k), "new": v}
            merged[k] = v
    users[email] = merged
    _save(db_path, db)
    return {"status": "updated" if changes else "no_change", "changes": changes}
