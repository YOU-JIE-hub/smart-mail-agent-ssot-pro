
from __future__ import annotations
import sqlite3, csv, pathlib, sys
DB = pathlib.Path("db/sma.sqlite"); DB.parent.mkdir(parents=True, exist_ok=True)

def migrate():
    con = sqlite3.connect(DB); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS actions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT, intent TEXT, action TEXT, status TEXT,
      artifact_path TEXT, ext TEXT, message TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      mail_id TEXT, ts TEXT, subject TEXT, body TEXT
    )""")
    con.commit(); con.close(); print("[DB] migrate ok")

def views():
    con=sqlite3.connect(DB); cur=con.cursor()
    cur.execute("DROP VIEW IF EXISTS v_intent_daily")
    cur.execute("DROP VIEW IF EXISTS v_hitl_rate;
    DROP VIEW IF EXISTS v_ml_signals")
    cur.execute("DROP VIEW IF EXISTS v_kie_quality")
    cur.execute("DROP VIEW IF EXISTS v_spam_quality")
    cur.execute("""
    CREATE VIEW v_intent_daily AS
    SELECT substr(ts,1,10) AS day, COALESCE(intent,'') AS intent, COUNT(*) AS n
    FROM actions GROUP BY 1,2 ORDER BY 1 DESC, 3 DESC
    """)
    cur.execute("""
    CREATE VIEW v_ml_signals AS
    SELECT
      substr(ts,1,8) AS day,
      json_extract(ext,'$.ml_top1') AS top1,
      CAST(json_extract(ext,'$.ml_conf') AS REAL) AS conf1,
      COALESCE(
        CAST(json_extract(ext,'$.ml_margin') AS REAL),
        CAST(json_extract(ext,'$.ml_conf') AS REAL) - COALESCE(CAST(json_extract(ext,'$.raw.top2.conf') AS REAL),0)
      ) AS margin
    FROM actions WHERE action='ml_signal';

    CREATE VIEW v_hitl_rate AS
    WITH daily AS (
      SELECT substr(ts,1,10) AS day,
             COUNT(*) AS total,
             SUM(CASE WHEN COALESCE(intent,'')='' THEN 1 ELSE 0 END) AS hitl
      FROM actions GROUP BY 1
    )
    SELECT day,total,hitl, ROUND(CASE WHEN total>0 THEN 1.0*hitl/total ELSE 0 END,2) AS rate
    FROM daily ORDER BY day DESC
    """)
    
    # v_kie_quality：每天取最新一筆 kie_runs
    cur.execute("""
    CREATE VIEW v_kie_quality AS
    WITH ranked AS (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY substr(ts,1,8) ORDER BY ts DESC) rn
      FROM kie_runs
    )
    SELECT substr(ts,1,8) AS day, exact_micro_f1, overlap_micro_f1, exact_macro_f1, overlap_macro_f1
    FROM ranked WHERE rn=1
    """)
    # v_spam_quality：每天取最新一筆 spam_runs
    cur.execute("""
    CREATE VIEW v_spam_quality AS
    WITH ranked AS (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY substr(ts,1,8) ORDER BY ts DESC) rn
      FROM spam_runs
    )
    SELECT substr(ts,1,8) AS day, source, macro_f1
    FROM ranked WHERE rn=1
    """)
    con.commit(); con.close(); print("[DB] views ok")


def snapshot():
    con=sqlite3.connect(DB); cur=con.cursor()
    outdir = pathlib.Path("reports_auto/db_reports"); outdir.mkdir(parents=True, exist_ok=True)
    # actions tail
    rows = cur.execute("SELECT ts,intent,action,status,artifact_path FROM actions ORDER BY id DESC LIMIT 50").fetchall()
    with open(outdir/"actions_tail.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["ts","intent","action","status","artifact_path"]); w.writerows(rows)
    # v_intent_daily
    try:
        rows = cur.execute("SELECT * FROM v_intent_daily ORDER BY day DESC, n DESC LIMIT 50").fetchall()
        with open(outdir/"v_intent_daily.csv","w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["day","intent","n"]); w.writerows(rows)
    except Exception: pass
    # v_hitl_rate
    try:
        rows = cur.execute("SELECT * FROM v_hitl_rate ORDER BY day DESC LIMIT 50").fetchall()
        with open(outdir/"v_hitl_rate.csv","w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["day","total","hitl","rate"]); w.writerows(rows)
    except Exception: pass
    con.close(); print("[DB] snapshot ok -> reports_auto/db_reports")

if __name__=="__main__":
    arg = sys.argv[1] if len(sys.argv)>1 else "migrate"
    {"migrate":migrate, "views":views, "snapshot":snapshot}.get(arg, migrate)()
