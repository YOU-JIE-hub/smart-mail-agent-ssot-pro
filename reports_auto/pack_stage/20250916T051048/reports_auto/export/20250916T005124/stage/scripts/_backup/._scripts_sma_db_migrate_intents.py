#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
確保 sqlite: db/sma.sqlite 內有標準表結構，避免後處理抓不到欄位。
- 建立（若不存在）：
    intent_preds(case_id TEXT, pred TEXT, conf REAL, ts TEXT)
    kie_spans(case_id TEXT, key TEXT, value TEXT, start INT, end INT)
    err_log(ts TEXT, case_id TEXT, err TEXT)
- 若欄位缺漏則以 ALTER TABLE 補上。
"""
import sqlite3, sys, time, os
DB="db/sma.sqlite"
os.makedirs("db", exist_ok=True)
con=sqlite3.connect(DB); cur=con.cursor()

def ensure_table(sql_create):
    cur.execute(sql_create)

def add_col_if_missing(table, col, decl):
    cur.execute(f"PRAGMA table_info({table})")
    cols=[r[1] for r in cur.fetchall()]
    if col not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

# intent_preds
ensure_table("""CREATE TABLE IF NOT EXISTS intent_preds(
    case_id TEXT, pred TEXT, conf REAL, ts TEXT
)""")
for c,decl in [("case_id","TEXT"),("pred","TEXT"),("conf","REAL"),("ts","TEXT")]:
    add_col_if_missing("intent_preds", c, decl)

# kie_spans
ensure_table("""CREATE TABLE IF NOT EXISTS kie_spans(
    case_id TEXT, key TEXT, value TEXT, start INT, end INT
)""")
for c,decl in [("case_id","TEXT"),("key","TEXT"),("value","TEXT"),("start","INT"),("end","INT")]:
    add_col_if_missing("kie_spans", c, decl)

# err_log
ensure_table("""CREATE TABLE IF NOT EXISTS err_log(
    ts TEXT, case_id TEXT, err TEXT
)""")
for c,decl in [("ts","TEXT"),("case_id","TEXT"),("err","TEXT")]:
    add_col_if_missing("err_log", c, decl)

con.commit(); con.close()
print("[OK] DB migrated:", DB)
