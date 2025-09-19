#!/usr/bin/env python3
import argparse, json, sqlite3, sys
from pathlib import Path
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run-dir", required=True)
    args=ap.parse_args()
    run_dir=Path(args.run_dir); run_ts=run_dir.name
    plan=run_dir/"actions_plan.ndjson"
    if not plan.exists():
        print(f"[FATAL] not found: {plan}", file=sys.stderr); sys.exit(3)
    conn=sqlite3.connect(args.db); cur=conn.cursor()
    ins=0; skip=0
    with open(plan,"r",encoding="utf-8") as f:
        for ln in f:
            ln=ln.strip()
            if not ln: continue
            obj=json.loads(ln)
            case_id=obj.get("case_id")
            for st in obj.get("steps",[]):
                if not st.get("hil_gate"): 
                    continue
                a_type=st.get("type") or "Unknown"
                # 已有 pending/approved/rejected 就跳過同一 run_ts/case/action_type
                row=cur.execute("""
                  SELECT id,status FROM approvals
                  WHERE run_ts=? AND case_id=? AND action_type=?
                """,(run_ts,case_id,a_type)).fetchone()
                if row: 
                    skip+=1; 
                    continue
                cur.execute("""
                  INSERT INTO approvals(run_ts,case_id,action_type,status,note)
                  VALUES(?,?,?,?,?)
                """,(run_ts,case_id,a_type,'pending','seeded from plan'))
                ins+=1
    conn.commit()
    print(f"[OK] approvals seeded: inserted={ins}, skipped_existing={skip}, run_ts={run_ts}")
if __name__=="__main__": main()
