import os
import pathlib
import sqlite3
from typing import Any

DEFAULT_DB = os.getenv("SMA_DB_PATH", "reports_auto/sma.sqlite3")
DDL = {
    "tables": [
        (
            """CREATE TABLE IF NOT EXISTS dead_letters(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, payload TEXT, reason TEXT, retry_after TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, po_no TEXT, items_json TEXT, amount TEXT, currency TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS shipments(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, tracking_no TEXT, carrier TEXT, items_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS rmas(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, rma_no TEXT, sn TEXT, reason TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS invoices(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, title TEXT, vat TEXT, amount TEXT, status TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS actions(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
  payload TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS actions_history(
  id INTEGER PRIMARY KEY, action_id INTEGER NOT NULL, old_status TEXT, new_status TEXT,
  changed_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(action_id) REFERENCES actions(id))"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS mails(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, subject TEXT, sender TEXT, body TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS errors(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, phase TEXT, message TEXT, trace TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS tickets(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, action_id INTEGER, data TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(action_id) REFERENCES actions(id))"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS answers(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, action_id INTEGER, content TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(action_id) REFERENCES actions(id))"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS changes(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, obj TEXT, before TEXT, after TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS quotes(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, action_id INTEGER, amount TEXT, currency TEXT, extra TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY(action_id) REFERENCES actions(id))"""
        ),
        (
            """CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY, idem TEXT NOT NULL, level TEXT, message TEXT, meta TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')) )"""
        ),
    ],
    "indexes": [
        "CREATE INDEX IF NOT EXISTS idx_dead_letters_when ON dead_letters(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_orders_po ON orders(po_no)",
        "CREATE INDEX IF NOT EXISTS idx_shipments_tracking ON shipments(tracking_no)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_actions_idem ON actions(idem)",
        "CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_mails_idem ON mails(idem)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_errors_idem ON errors(idem)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_tickets_idem ON tickets(idem)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_answers_idem ON answers(idem)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_changes_idem ON changes(idem)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_quotes_idem ON quotes(idem)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_alerts_idem ON alerts(idem)",
    ],
    "triggers": [
        (
            """CREATE TRIGGER IF NOT EXISTS trg_actions_status
AFTER UPDATE OF status ON actions FOR EACH ROW
WHEN OLD.status IS NOT NEW.status
BEGIN
  INSERT INTO actions_history(action_id, old_status, new_status, changed_at)
  VALUES (OLD.id, OLD.status, NEW.status, datetime('now'));
  UPDATE actions SET updated_at = datetime('now') WHERE id = NEW.id;
END"""
        )
    ],
    "views": [
        (
            """CREATE VIEW IF NOT EXISTS v_actions_summary AS
SELECT json_extract(a.payload, '$.intent.intent') AS intent,
       COUNT(*) AS cnt
FROM actions a GROUP BY intent"""
        ),
        (
            """CREATE VIEW IF NOT EXISTS v_quality_gaps AS
SELECT json_extract(a.payload, '$.intent.intent') AS intent,
       AVG(CASE WHEN json_extract(a.payload, '$.kie.coverage.amount')=1 THEN 1 ELSE 0 END) AS cov_amount,
       AVG(CASE WHEN json_extract(a.payload, '$.kie.coverage.vat')=1 THEN 1 ELSE 0 END) AS cov_vat
FROM actions a GROUP BY intent"""
        ),
        (
            """CREATE VIEW IF NOT EXISTS v_tickets AS
SELECT t.id, t.idem, t.created_at, a.status,
       json_extract(t.data,'$.title') AS title, json_extract(t.data,'$.amount') AS amount
FROM tickets t LEFT JOIN actions a ON a.id = t.action_id"""
        ),
        (
            """CREATE VIEW IF NOT EXISTS v_answers AS
SELECT ans.id, ans.idem, ans.created_at, a.status, substr(ans.content, 1, 200) AS preview
FROM answers ans LEFT JOIN actions a ON a.id = ans.action_id"""
        ),
    ],
}


def ensure_schema(db_path: str = DEFAULT_DB) -> dict[str, Any]:
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()
    created = {"tables": 0, "indexes": 0, "triggers": 0, "views": 0}
    for sql in DDL["tables"]:
        cur.execute(sql)
        created["tables"] += 1
    for sql in DDL["indexes"]:
        cur.execute(sql)
        created["indexes"] += 1
    for sql in DDL["triggers"]:
        cur.execute(sql)
        created["triggers"] += 1
    for sql in DDL["views"]:
        cur.execute(sql)
        created["views"] += 1
    conn.commit()
    return {"db_path": db_path, "created": created}


def ingest_actions_jsonl(conn: sqlite3.Connection, jsonl_path: str) -> int:
    n = 0
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            import json as _json

            obj = _json.loads(line)
            idem = f"act:{obj.get('id')}"
            status = obj.get("status", "queued")
            payload = _json.dumps(obj, ensure_ascii=False)
            conn.execute(
                """INSERT INTO actions(idem, status, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(idem) DO UPDATE SET status=excluded.status, payload=excluded.payload, updated_at=datetime('now')""",
                (idem, status, payload),
            )
            n += 1
    conn.commit()
    return n


def snapshot_schema(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE type IN ('table','index','trigger','view') ORDER BY type, name"
    ).fetchall()
    out = []
    for typ, name, sql in rows:
        out.append(f"### {typ.upper()} `{name}`\n```\n{sql or ''}\n```\n")
    return "\n".join(out)


def dist_actions(conn: sqlite3.Connection) -> dict[str, int]:
    d = {}
    for s, c in conn.execute("SELECT COALESCE(status,'queued') AS s, COUNT(*) FROM actions GROUP BY s"):
        d[s] = int(c)
    for k in ("done", "error", "queued"):
        d.setdefault(k, 0)
    return d
