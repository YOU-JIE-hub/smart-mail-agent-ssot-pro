#!/usr/bin/env python3
import sqlite3, sys, argparse, re, time

REQ_COLS = ["id","run_ts","case_id","action_type","status","note","created_at","decided_at"]
DDL = """
CREATE TABLE approvals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_ts TEXT,
  case_id TEXT,
  action_type TEXT,
  status TEXT CHECK(status IN ('pending','approved','rejected')) DEFAULT 'pending',
  note TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  decided_at TEXT
);
"""
INDEXES = [
  "CREATE INDEX IF NOT EXISTS idx_approvals_run ON approvals(run_ts);",
  "CREATE INDEX IF NOT EXISTS idx_approvals_case ON approvals(case_id);",
  "CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);"
]

def table_exists(conn, name:str)->bool:
  return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None

def view_list(conn):
  return conn.execute("SELECT name, sql FROM sqlite_master WHERE type='view' AND sql IS NOT NULL").fetchall()

def views_ref_table(conn, table:str):
  pat = re.compile(r'\b(from|join)\s+("?' + re.escape(table) + r'"?|\[' + re.escape(table) + r'\])\b', re.I)
  out=[]
  for name, sql in view_list(conn):
    if sql and pat.search(sql):
      out.append((name, sql))
  return out

def cols(conn, table):
  return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]

def create_fresh(conn):
  conn.executescript(DDL)
  for s in INDEXES: conn.execute(s)

def safe_drop_temp(conn):
  cur = conn.cursor()
  for t in ("approvals_new","approvals_old"):
    cur.execute(f"DROP TABLE IF EXISTS {t}")

def migrate(conn):
  cur = conn.cursor()
  cur.execute("PRAGMA foreign_keys=OFF;")
  cur.execute("PRAGMA legacy_alter_table=ON;")
  safe_drop_temp(conn)

  # 已有且符合新制就直接通過
  if table_exists(conn, "approvals"):
    have = cols(conn, "approvals")
    if set(REQ_COLS).issubset(have):
      print("[OK] approvals schema OK")
      return

  # 找出依賴 approvals 的 views，先卸載
  deps = views_ref_table(conn, "approvals")
  cur.execute("BEGIN IMMEDIATE;")
  for name,_ in deps:
    cur.execute(f"DROP VIEW IF EXISTS {name}")
  conn.commit()

  # 重新進入遷移交易
  cur.execute("BEGIN IMMEDIATE;")
  safe_drop_temp(conn)

  legacy_name = None
  if table_exists(conn, "approvals"):
    # 把舊 approvals 改名留存
    legacy_name = "approvals_legacy_" + time.strftime("%Y%m%dT%H%M%S")
    cur.execute(f"ALTER TABLE approvals RENAME TO {legacy_name}")

  # 建立新制 approvals
  cur.executescript(DDL)
  for s in INDEXES: cur.execute(s)

  # 若有舊表，把能對應的欄位搬過來
  if legacy_name:
    have = cols(conn, legacy_name)
    # 來源可能是你目前看到的舊格式：case_id, field, old_value, new_value, decision, approver, approved_at, run_ts
    # 做合理映射：decision -> status，其他湊成 note
    def has(c): return c in have
    sel = []
    sel.append("NULL AS id")
    sel.append("run_ts" if has("run_ts") else "NULL AS run_ts")
    sel.append("case_id" if has("case_id") else "NULL AS case_id")
    # 沒 action_type 的歷史資料先置 NULL（之後一鍵流程會自己補新的 pending approvals）
    sel.append("NULL AS action_type")
    if has("status"):
      # 若舊表本來就有 status
      sel.append("""CASE lower(status)
                      WHEN 'approved' THEN 'approved'
                      WHEN 'rejected' THEN 'rejected'
                      WHEN 'pending'  THEN 'pending'
                      ELSE 'pending' END AS status""")
    elif has("decision"):
      sel.append("""CASE lower(decision)
                      WHEN 'approved' THEN 'approved'
                      WHEN 'approve'  THEN 'approved'
                      WHEN 'ok'       THEN 'approved'
                      WHEN 'rejected' THEN 'rejected'
                      WHEN 'reject'   THEN 'rejected'
                      ELSE 'pending' END AS status""")
    else:
      sel.append("'pending' AS status")
    # note：盡量保留舊欄位訊息
    if has("note"):
      sel.append("note")
    elif all(has(c) for c in ("field","old_value","new_value")):
      sel.append("(field||':'||COALESCE(old_value,'')||'→'||COALESCE(new_value,'')) AS note")
    else:
      sel.append("NULL AS note")
    sel.append("created_at" if has("created_at") else ( "approved_at AS created_at" if has("approved_at") else "datetime('now') AS created_at"))
    sel.append("decided_at" if has("decided_at") else ( "approved_at AS decided_at" if has("approved_at") else "NULL AS decided_at"))

    cur.execute(f"INSERT INTO approvals ({', '.join(REQ_COLS)}) SELECT {', '.join(sel)} FROM {legacy_name}")

  conn.commit()

  # 還原 views
  cur.execute("BEGIN IMMEDIATE;")
  for name, sql in deps:
    cur.execute(sql)
  conn.commit()
  print(f"[OK] approvals ready (legacy kept as {legacy_name or 'none'}; views reinstated: {', '.join(n for n,_ in deps) or 'none'})")

def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--db", default="db/sma.sqlite")
  args = ap.parse_args()
  conn = sqlite3.connect(args.db)
  try:
    migrate(conn)
  finally:
    conn.close()

if __name__ == "__main__":
  main()
