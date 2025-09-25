from __future__ import annotations
import sqlite3, sys, os
from pathlib import Path

DB=Path(sys.argv[1] if len(sys.argv)>1 else "db/sma.sqlite")
DB.parent.mkdir(parents=True, exist_ok=True)
con=sqlite3.connect(DB); cur=con.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
if not cur.execute("SELECT COUNT(1) FROM schema_version").fetchone()[0]:
    cur.execute("INSERT INTO schema_version(version) VALUES (0)")
con.commit()

def v(): return cur.execute("SELECT version FROM schema_version").fetchone()[0]
def setv(n): cur.execute("UPDATE schema_version SET version=?", (n,)); con.commit()

ver=v()

# v1: create actions if not exists
if ver<1:
    cur.execute("""
    CREATE TABLE IF NOT EXISTS actions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      run_ts TEXT, case_id TEXT, action TEXT, status TEXT,
      payload_ref TEXT, idempotency_key TEXT, created_at TEXT
    )""")
    setv(1); ver=1

# v2: add meta_json column
if ver<2:
    try: cur.execute("ALTER TABLE actions ADD COLUMN meta_json TEXT")
    except sqlite3.OperationalError: pass
    setv(2); ver=2

# v3: unique index on idempotency_key
if ver<3:
    try: cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_actions_idem ON actions(idempotency_key)")
    except sqlite3.OperationalError: pass
    setv(3); ver=3

con.commit(); con.close()
print(f"[OK] migrated -> v{ver} ({DB})")
