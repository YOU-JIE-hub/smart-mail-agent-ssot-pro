from __future__ import annotations
import sqlite3, os, pathlib

SQL = [
  # approvals gate
  """CREATE TABLE IF NOT EXISTS approvals(
       run_ts TEXT, case_id TEXT, required INTEGER,
       approved_by TEXT, approved_at TEXT,
       PRIMARY KEY(run_ts, case_id)
     );""",
  # idempotency key column (ignore errors if exists)
  """ALTER TABLE actions ADD COLUMN idempotency_key TEXT;""",
  # unique index
  """CREATE UNIQUE INDEX IF NOT EXISTS ux_actions_idem ON actions(idempotency_key);""",
]

def ensure_constraints(db_path: str) -> None:
  p = pathlib.Path(db_path); p.parent.mkdir(parents=True, exist_ok=True)
  conn = sqlite3.connect(db_path)
  try:
    cur = conn.cursor()
    for stmt in SQL:
      try:
        cur.execute(stmt)
      except sqlite3.OperationalError as e:
        # column exists / benign
        if "duplicate column name" in str(e) or "already exists" in str(e): pass
        else: raise
    conn.commit()
  finally:
    conn.close()
