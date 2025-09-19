#!/usr/bin/env python3
import argparse, sqlite3, time
NOW=lambda: time.strftime("%Y-%m-%dT%H:%M:%S")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--action-type", default="SendEmail")
    args=ap.parse_args()
    run_ts=args.run_dir.rstrip("/").split("/")[-1]
    conn=sqlite3.connect(args.db); cur=conn.cursor()
    # approvals → 全部核准
    cur.execute("""UPDATE approvals
                     SET status='approved', decided_at=?
                   WHERE run_ts=? AND (action_type=? OR action_type IS NULL) AND status='pending';""",
                (NOW(), run_ts, args.action_type))
    approved=cur.rowcount
    # actions → 解鎖
    cur.execute("""UPDATE actions
                     SET status='planned', updated_at=?
                   WHERE run_ts=? AND COALESCE(action_type,action)=? AND status='skipped_by_hil';""",
                (NOW(), run_ts, args.action_type))
    reset=cur.rowcount
    conn.commit(); conn.close()
    print(f"[OK] HIL approve-all run_ts={run_ts}, type={args.action_type} → approvals={approved}, actions_reset={reset}")
if __name__=="__main__": main()
