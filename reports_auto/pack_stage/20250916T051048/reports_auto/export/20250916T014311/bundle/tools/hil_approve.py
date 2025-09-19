#!/usr/bin/env python3
import argparse, sqlite3, time, sys
def NOW(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def ensure_schema(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS approvals(
        run_ts TEXT NOT NULL,
        case_id TEXT NOT NULL,
        action_type TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        decided_at TEXT,
        note TEXT
    );""")
    try: cur.execute("ALTER TABLE approvals ADD COLUMN note TEXT")
    except sqlite3.Error: pass
def coalesce_action_col(): return "COALESCE(action_type, action)"
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run-dir"); ap.add_argument("--run-ts")
    ap.add_argument("--case-id"); ap.add_argument("--action-type", default="SendEmail")
    ap.add_argument("--approve-all", action="store_true")
    args = ap.parse_args()
    run_ts = args.run_ts or (args.run_dir.rstrip("/").split("/")[-1] if args.run_dir else None)
    if not run_ts: print("[FATAL] need --run-dir or --run-ts", file=sys.stderr); sys.exit(2)
    conn = sqlite3.connect(args.db); conn.row_factory = sqlite3.Row
    cur = conn.cursor(); ensure_schema(cur)
    cur.execute("SELECT COUNT(*) c FROM approvals WHERE run_ts=?", (run_ts,))
    if (cur.fetchone()["c"] or 0) == 0:
        print(f"[OK] no approvals row for run {run_ts} (nothing to approve)"); sys.exit(0)
    if args.approve_all:
        cur.execute("""UPDATE approvals SET status='approved', decided_at=?
                       WHERE run_ts=? AND status='pending' AND (action_type=? OR action_type IS NULL)""",
                    (NOW(), run_ts, args.action_type))
        a_cnt = cur.rowcount
        cur.execute(f"""UPDATE actions SET status='planned', updated_at=?
                        WHERE run_ts=? AND case_id IN (
                          SELECT case_id FROM approvals WHERE run_ts=? AND status='approved' AND (action_type=? OR action_type IS NULL)
                        ) AND {coalesce_action_col()}=? AND status='skipped_by_hil'""",
                    (NOW(), run_ts, run_ts, args.action_type, args.action_type))
        r_cnt = cur.rowcount; conn.commit()
        print(f"[OK] approve-all: approvals={a_cnt}, actions_reset={r_cnt}, run_ts={run_ts}, type={args.action_type}")
        return
    if not args.case_id: print("[FATAL] need --case-id (or --approve-all)", file=sys.stderr); sys.exit(2)
    cur.execute("""UPDATE approvals SET status='approved', decided_at=?
                   WHERE run_ts=? AND case_id=? AND status='pending' AND (action_type=? OR action_type IS NULL)""",
                (NOW(), run_ts, args.case_id, args.action_type))
    a_cnt = cur.rowcount
    cur.execute(f"""UPDATE actions SET status='planned', updated_at=?
                    WHERE run_ts=? AND case_id=? AND {coalesce_action_col()}=? AND status='skipped_by_hil'""",
                (NOW(), run_ts, args.case_id, args.action_type))
    r_cnt = cur.rowcount; conn.commit()
    print(f"[OK] approved: approvals={a_cnt}, actions_reset={r_cnt}, run_ts={run_ts}, case={args.case_id}, type={args.action_type}")
if __name__ == "__main__": main()
