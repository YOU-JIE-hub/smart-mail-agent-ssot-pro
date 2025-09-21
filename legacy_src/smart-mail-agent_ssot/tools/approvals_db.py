from __future__ import annotations
import sqlite3, argparse, sys, json, time
def conn(db): 
    con=sqlite3.connect(db); cur=con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS approvals(
      run_ts TEXT, case_id TEXT, approved_by TEXT, approved_at TEXT
    )"""); con.commit(); return con
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("cmd", choices=["list","approve_all","approve"])
    ap.add_argument("--run-ts"); ap.add_argument("--case-id")
    ap.add_argument("--by", default="owner")
    args=ap.parse_args(); con=conn(args.db); cur=con.cursor()
    if args.cmd=="list":
        q="SELECT run_ts, case_id, approved_by, approved_at FROM approvals ORDER BY approved_at DESC"
        for r in cur.execute(q): print("\t".join(r))
    elif args.cmd=="approve_all":
        assert args.run_ts, "--run-ts required"
        cur.execute("""INSERT INTO approvals(run_ts,case_id,approved_by,approved_at)
            SELECT ?, case_id, ?, datetime('now') FROM (
              SELECT DISTINCT ? as run_ts, replace(name,'.txt','') as case_id
              FROM pragma_table_info('approvals') WHERE 1=0
            )""", (args.run_ts, args.by, args.run_ts))
        # 上面 dummy；實際批核交由 hil_gate_db 產 .approved，因此這裡提供單筆：
        print("[INFO] prefer using hil_approve_all.sh for mass approval")
    elif args.cmd=="approve":
        assert args.run_ts and args.case_id, "--run-ts/--case-id required"
        cur.execute("INSERT INTO approvals VALUES (?,?,?,datetime('now'))",
                    (args.run_ts, args.case_id, args.by))
        print("[OK] approved", args.run_ts, args.case_id)
    con.commit(); con.close()
if __name__=="__main__": main()
