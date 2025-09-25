from __future__ import annotations
from pathlib import Path
import sqlite3, argparse, time

def ensure_conn(db_path:str):
    return sqlite3.connect(db_path)

def try_create_table(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_ts TEXT, 
        case_id TEXT, 
        action TEXT, 
        status TEXT,
        payload_ref TEXT, 
        idempotency_key TEXT, 
        created_at TEXT
    )
    """)

def backfill(run_dir:Path, db_path:str):
    sent_dir = run_dir / "rpa_out" / "email_sent"
    if not sent_dir.exists(): 
        print("[SKIP] no email_sent dir:", sent_dir); return 0
    emls = sorted(sent_dir.glob("*.eml"))
    if not emls:
        print("[SKIP] no .eml files"); return 0
    run_ts = run_dir.name
    con=ensure_conn(db_path); cur=con.cursor()
    try_create_table(cur)
    inserted=0
    for eml in emls:
        idem=f"{run_ts}:{eml.stem}:SendEmail"
        cur.execute("select count(1) from actions where idempotency_key=?", (idem,))
        if cur.fetchone()[0]>0: 
            continue
        cur.execute("insert into actions(run_ts, case_id, action, status, payload_ref, idempotency_key, created_at) values (?,?,?,?,?,?,?)",
                    (run_ts, eml.stem, "SendEmail", "succeeded", str(eml), idem, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
        inserted+=1
    con.commit(); con.close()
    print(f"[OK] backfilled {inserted} rows into actions")
    return inserted

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--db", default="db/sma.sqlite")
    a=ap.parse_args()
    backfill(Path(a.run_dir), a.db)
