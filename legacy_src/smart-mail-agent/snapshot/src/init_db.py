from __future__ import annotations

import sqlite3
from pathlib import Path


def _ensure(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)


def init_users_db(path: str | Path = "data/users.db") -> str:
    p = Path(path)
    _ensure(p)
    with sqlite3.connect(p) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE,
            phone TEXT,
            address TEXT
        )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS diff_log(
            id INTEGER PRIMARY KEY,
            email TEXT,
            field TEXT,
            old_value TEXT,
            new_value TEXT,
            ts TEXT
        )"""
        )
    return str(p)


def init_emails_log_db(path: str | Path = "data/emails_log.db") -> str:
    p = Path(path)
    _ensure(p)
    with sqlite3.connect(p) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS emails_log(
            id INTEGER PRIMARY KEY,
            subject TEXT, content TEXT, summary TEXT,
            predicted_label TEXT, confidence REAL,
            action TEXT, error TEXT, ts TEXT
        )"""
        )
    return str(p)


def init_processed_mails_db(path: str | Path = "data/processed_mails.db") -> str:
    p = Path(path)
    _ensure(p)
    with sqlite3.connect(p) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS processed_mails(
            id INTEGER PRIMARY KEY,
            message_id TEXT, ts TEXT
        )"""
        )
    return str(p)


def init_tickets_db(path: str | Path = "data/support_tickets.db") -> str:
    p = Path(path)
    _ensure(p)
    with sqlite3.connect(p) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS tickets(
            id INTEGER PRIMARY KEY,
            email TEXT, subject TEXT, content TEXT,
            category TEXT, confidence REAL, status TEXT,
            summary TEXT, ts TEXT
        )"""
        )
    return str(p)
