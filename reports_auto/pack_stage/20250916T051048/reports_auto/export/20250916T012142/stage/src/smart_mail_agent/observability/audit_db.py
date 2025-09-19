from __future__ import annotations

import json
import os
import sqlite3
import time
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Any


# ---------- Path helpers ----------
def _root() -> Path:
    return Path(os.environ.get("SMA_ROOT", Path(__file__).resolve().parents[3]))


def _db_path() -> Path:
    p = os.environ.get("SMA_DB_PATH")
    return Path(p) if p else _root() / "reports_auto" / "audit.sqlite3"


DEFAULT_DB: Path = _db_path()


def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


# ---------- Schema ----------
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS mails(
  mail_id   TEXT PRIMARY KEY,
  subject   TEXT,
  ts        INTEGER
);

CREATE TABLE IF NOT EXISTS metrics(
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          INTEGER,
  stage       TEXT,
  duration_ms INTEGER,
  ok          INTEGER,
  mail_id     TEXT,
  extra       TEXT
);
CREATE INDEX IF NOT EXISTS idx_metrics_ts    ON metrics(ts);
CREATE INDEX IF NOT EXISTS idx_metrics_stage ON metrics(stage);

CREATE TABLE IF NOT EXISTS actions(
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  ts              INTEGER,
  mail_id         TEXT,
  action          TEXT,
  priority        TEXT,
  queue           TEXT,
  idempotency_key TEXT,
  payload         TEXT
);
CREATE INDEX  IF NOT EXISTS idx_actions_ts   ON actions(ts);
CREATE INDEX  IF NOT EXISTS idx_actions_mail ON actions(mail_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_actions_idem ON actions(idempotency_key);

CREATE TABLE IF NOT EXISTS triage(
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      INTEGER,
  mail_id TEXT,
  reason  TEXT,
  note    TEXT,
  extra   TEXT
);
CREATE INDEX IF NOT EXISTS idx_triage_ts   ON triage(ts);
CREATE INDEX IF NOT EXISTS idx_triage_mail ON triage(mail_id);

CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, mail_id TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS quotes (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, mail_id TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS answers(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, mail_id TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, mail_id TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, mail_id TEXT, payload TEXT);

CREATE TABLE IF NOT EXISTS errors(
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       INTEGER,
  stage    TEXT,
  mail_id  TEXT,
  exc_type TEXT,
  message  TEXT,
  details  TEXT,
  extra    TEXT
);
CREATE INDEX IF NOT EXISTS idx_errors_ts    ON errors(ts);
CREATE INDEX IF NOT EXISTS idx_errors_stage ON errors(stage);
"""


def open_db(db: Path | None = None) -> sqlite3.Connection:
    db_path = Path(db or DEFAULT_DB)
    _ensure_dir(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _have_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)


def ensure_schema(db: Path | None = None) -> Path:
    db_path = Path(db or DEFAULT_DB)
    _ensure_dir(db_path)
    with open_db(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        # —— migrations：補舊 DB 缺的欄位與索引 —— #
        if not _have_column(conn, "actions", "idempotency_key"):
            conn.execute("ALTER TABLE actions ADD COLUMN idempotency_key TEXT")
        if not _have_column(conn, "actions", "payload"):
            conn.execute("ALTER TABLE actions ADD COLUMN payload TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_actions_idem ON actions(idempotency_key)")
        conn.commit()
    return db_path


def _jsonify_inplace(row: dict) -> None:
    for k, v in list(row.items()):
        if isinstance(v, dict | list | tuple):
            row[k] = json.dumps(v, ensure_ascii=False)


def insert_row(table: str, data: Mapping[str, Any], db: Path | None = None) -> int:
    """
    冪等策略：
      - actions 且帶 idempotency_key -> INSERT OR IGNORE
      - mails 且帶 mail_id          -> INSERT OR IGNORE
      - 其他表 -> 一般 INSERT
    """
    row = dict(data)
    row.setdefault("ts", int(time.time()))
    _jsonify_inplace(row)

    cols = ", ".join(row.keys())
    qs = ", ".join(["?"] * len(row))

    do_ignore = (table == "actions" and "idempotency_key" in row) or (table == "mails" and "mail_id" in row)
    sql = (
        f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({qs})"
        if do_ignore
        else f"INSERT INTO {table} ({cols}) VALUES ({qs})"
    )

    with open_db(db) as conn:
        cur = conn.execute(sql, tuple(row.values()))
        conn.commit()
        return int(cur.lastrowid or 0)


def write_err_log(
    stage: str, *args, mail_id: str | None = None, extra: dict | None = None, db: Path | None = None
) -> Path:
    """
    兼容兩種呼叫：
      A) write_err_log(stage, exc, *, mail_id=?, extra=?, db=?)
      B) write_err_log(stage, level, message, extra_dict)
    """
    exc: BaseException | None = None
    if args:
        first = args[0]
        if isinstance(first, BaseException):
            exc = first
            if len(args) >= 2 and extra is None and isinstance(args[1], dict):
                extra = args[1]  # type: ignore[assignment]
        else:
            level = str(first) if len(args) >= 1 else "ERROR"
            message = str(args[1]) if len(args) >= 2 else ""
            if len(args) >= 3 and extra is None and isinstance(args[2], dict):
                extra = args[2]  # type: ignore[assignment]

            class _CompatError(Exception):
                pass

            exc = _CompatError(f"{level}: {message}")

    if extra and mail_id is None and isinstance(extra, dict):
        mi = extra.get("mail_id")
        if isinstance(mi, str):
            mail_id = mi

    if exc is None:
        exc = Exception("write_err_log called without exception/message")

    ts = int(time.time())
    exc_type = type(exc).__name__
    message = str(exc)
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    try:
        ensure_schema(db)
        insert_row(
            "errors",
            {
                "ts": ts,
                "stage": stage,
                "mail_id": mail_id,
                "exc_type": exc_type,
                "message": message,
                "details": details,
                "extra": extra or {},
            },
            db=db,
        )
    except Exception:
        pass

    logs_dir = _root() / "reports_auto" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    fp = logs_dir / f"CRASH_{time.strftime('%Y%m%dT%H%M%S', time.gmtime(ts))}.log"
    with fp.open("a", encoding="utf-8") as f:
        f.write("# CRASH REPORT (Exception)\n\n")
        f.write("## STAGE\n" + stage + "\n\n")
        f.write("## MAIL_ID\n" + str(mail_id) + "\n\n")
        f.write("## TYPE\n" + exc_type + "\n\n")
        f.write("## MESSAGE\n" + message + "\n\n")
        f.write("## TRACEBACK\n" + details + "\n")
        if extra:
            f.write("## EXTRA\n" + json.dumps(extra, ensure_ascii=False, indent=2) + "\n")
    return fp


class AuditDB:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB)
        ensure_schema(self.db_path)

    def ensure_schema(self) -> Path:
        return ensure_schema(self.db_path)

    def insert_row(self, table: str, data: Mapping[str, Any]) -> int:
        return insert_row(table, data, db=self.db_path)

    def insert(self, table: str, data: Mapping[str, Any]) -> int:
        return self.insert_row(table, data)

    def write_err_log(self, stage: str, *args, **kw) -> Path:
        if "db" not in kw:
            kw["db"] = self.db_path
        return write_err_log(stage, *args, **kw)

    def log_error(self, stage: str, *args, **kw) -> Path:
        return self.write_err_log(stage, *args, **kw)


__all__ = [
    "DEFAULT_DB",
    "open_db",
    "ensure_schema",
    "insert_row",
    "write_err_log",
    "AuditDB",
]
