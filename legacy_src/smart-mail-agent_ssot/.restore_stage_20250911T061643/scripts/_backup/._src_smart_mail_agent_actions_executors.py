from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

# 可選：引用可用的行為器，不在此崩潰；缺少時用降級路徑
try:
    from .quote import do_quote  # type: ignore
except Exception:  # pragma: no cover
    do_quote = None

try:
    from .apology import send_apology  # type: ignore
except Exception:  # pragma: no cover
    send_apology = None  # type: ignore

ALLOW_SAFE_DEGRADE = os.environ.get("SMA_ALLOW_SAFE_DEGRADE", "0") == "1"


def _ensure_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS actions(
               id INTEGER PRIMARY KEY,
               idem TEXT,
               status TEXT,
               payload TEXT,
               created_at TEXT DEFAULT (datetime('now')),
               updated_at TEXT DEFAULT (datetime('now'))
           )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS answers(
               id INTEGER PRIMARY KEY,
               mail_id TEXT,
               intent TEXT,
               answer TEXT,
               status TEXT,
               idempotency_key TEXT UNIQUE,
               created_at TEXT DEFAULT (datetime('now'))
           )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS tickets(
               id INTEGER PRIMARY KEY,
               mail_id TEXT,
               title TEXT,
               severity TEXT,
               status TEXT,
               extra TEXT,
               idempotency_key TEXT UNIQUE,
               created_at TEXT DEFAULT (datetime('now'))
           )"""
    )
    conn.commit()
    conn.close()


def _persist_ticket(db: Path, mail_id: str, title: str, severity: str, key: str, extra: dict[str, Any]) -> None:
    _ensure_db(db)
    conn = sqlite3.connect(str(db))
    conn.execute(
        """INSERT OR IGNORE INTO tickets
           (mail_id,title,severity,status,extra,idempotency_key)
           VALUES(?, ?, ?, 'done', ?, ?)""",
        (mail_id, title, severity, json.dumps(extra, ensure_ascii=False), key),
    )
    conn.commit()
    conn.close()


def _persist_answer(db: Path, mail_id: str, intent: str, answer: str, key: str) -> None:
    _ensure_db(db)
    conn = sqlite3.connect(str(db))
    conn.execute(
        """INSERT OR IGNORE INTO answers
           (mail_id,intent,answer,status,idempotency_key)
           VALUES(?, ?, ?, 'done', ?)""",
        (mail_id, intent, answer, key),
    )
    conn.commit()
    conn.close()


def _fallback_done(payload: dict[str, Any], note: str) -> dict[str, Any]:
    return {"ok": True, "degraded": True, "note": note, "payload": payload}


def execute_action(
    *,
    db_path: str | Path,
    out_root: str | Path,
    name: str,
    payload: dict[str, Any],
    idem_key: str,
) -> dict[str, Any]:
    """
    最小可用執行器：在缺模組時不閃退，企業級需可降級。
    """
    t0 = time.time()
    db = Path(db_path)
    out_dir = Path(out_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    if name == "ticket_create":
        title = payload.get("title", "Tech Support")
        sev = payload.get("severity", "P3")
        mail_id = payload.get("mail_id", "?")
        _persist_ticket(db, mail_id, title, sev, idem_key, payload)
        return {"ok": True, "latency_ms": int((time.time() - t0) * 1000)}

    if name == "apology_send":
        if send_apology is None:
            if ALLOW_SAFE_DEGRADE:
                _persist_answer(db, payload.get("mail_id", "?"), "apology", "Degraded apology.", idem_key)
                return _fallback_done(payload, "apology module missing; degraded")
            raise RuntimeError("apology module missing")
        outbox = send_apology(None, payload.get("to", ""), payload.get("mail_id", "?"), idem_key)  # type: ignore
        return {"ok": True, "outbox": outbox, "latency_ms": int((time.time() - t0) * 1000)}

    if name == "quote_pdf_send":
        if do_quote is None:
            if ALLOW_SAFE_DEGRADE:
                return _fallback_done(payload, "quote module missing; degraded")
            raise RuntimeError("quote module missing")
        amount = float(payload.get("amount", 0.0))
        pdf = do_quote(  # type: ignore
            None,
            payload.get("mail_id", "?"),
            payload.get("to", ""),
            payload.get("items", []),
            amount,
            payload.get("currency", "TWD"),
            idem_key,
        )
        return {"ok": True, "pdf": pdf, "latency_ms": int((time.time() - t0) * 1000)}

    # 未知 action：直接降級
    return _fallback_done(payload, f"unknown action: {name}")
