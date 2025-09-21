from __future__ import annotations
from pathlib import Path
import argparse, json, sqlite3, shutil, time

def load_approvals(db:str, run_ts:str)->set[str]:
    if not Path(db).exists(): return set()
    con=sqlite3.connect(db); cur=con.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS approvals(run_ts TEXT, case_id TEXT, approved_by TEXT, approved_at TEXT)")
    cur.execute("SELECT case_id FROM approvals WHERE run_ts=?", (run_ts,))
    s={r[0] for r in cur.fetchall()}
    con.close(); return s

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--ndjson", required=True)
    ap.add_argument("--by", default="owner")
    args=ap.parse_args()
    run=Path(args.run_dir); run_ts=run.name
    outbox=run/"rpa_out"/"email_outbox"; blocked=run/"rpa_out"/"email_blocked"
    outbox.mkdir(parents=True, exist_ok=True); blocked.mkdir(parents=True, exist_ok=True)
    approved=load_approvals(args.db, run_ts)
    moved=0
    from smart_mail_agent.observability.ndjson_v2 import NDJSONLogger
    lg=NDJSONLogger(args.ndjson, default_run_ts=run_ts)
    lg.write(kind="runner", level="INFO", action="hil_start", result="ok")

    for txt in sorted(outbox.glob("*.txt")):
        cid=txt.stem
        if (outbox/(cid+".approved")).exists() or cid in approved: 
            continue
        shutil.move(str(txt), str(blocked/txt.name)); moved+=1
    lg.write(kind="runner", level="INFO", action="hil_blocked", result="blocked", moved=moved)
    lg.write(kind="runner", level="INFO", action="hil_done", result="ok", moved=moved)
    print(f"[OK] HIL gate -> moved {moved}")
if __name__=="__main__": main()
