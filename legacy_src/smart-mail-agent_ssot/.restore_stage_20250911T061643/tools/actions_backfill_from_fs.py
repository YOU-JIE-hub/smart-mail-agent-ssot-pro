#!/usr/bin/env python3
import argparse, sqlite3, time
from pathlib import Path

NOW = lambda: time.strftime("%Y-%m-%dT%H:%M:%S")

def action_cols(conn):
    try: return {r[1] for r in conn.execute("PRAGMA table_info(actions);")}
    except sqlite3.Error: return set()

def safe_update(conn, idem, *, status=None, payload_path=None, has_ended=False, verbose=False):
    c = action_cols(conn)
    sets, vals = [], []
    if status: sets.append('"status"=?'); vals.append(status)
    # 儲存 payload
    payload_col = "payload_ref" if "payload_ref" in c else ("payload_json" if "payload_json" in c else None)
    if payload_col and payload_path:
        sets.append(f'"{payload_col}"=?'); vals.append(payload_path)
    # 時戳
    now = NOW()
    if "updated_at" in c: sets.append('"updated_at"=?'); vals.append(now)
    if has_ended and "ended_at" in c: sets.append('"ended_at"=?'); vals.append(now)
    where = "idempotency_key=?"; vals.append(idem)
    sql = f"UPDATE actions SET {', '.join(sets)} WHERE {where}"
    if verbose: print(f"[DBG] SQL={sql} VALS={vals}")
    cur = conn.cursor(); cur.execute(sql, vals); conn.commit()
    return cur.rowcount

def idem_for(run_ts, artifact_id, action_type):  # 與你現有 backfill 相同策略
    return f"{run_ts}:{artifact_id}:{action_type}"

def mark_from_dir(conn, run_dir:Path, run_ts:str, sub:str, action_type:str, success_status:str, suffixes:set, verbose=False):
    base = run_dir/"rpa_out"/sub
    if not base.exists(): return 0
    n=0
    for p in sorted(base.iterdir()):
        if not any(str(p.name).endswith(sfx) for sfx in suffixes): continue
        art = p.stem
        idem = idem_for(run_ts, art, action_type)
        n += safe_update(conn, idem, status=success_status, payload_path=str(p), has_ended=True, verbose=verbose) or 0
        if verbose: print(f"[DBG] {action_type} {success_status} ← {p.name} → idem={idem}")
    return n

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("-v","--verbose", action="store_true")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_ts  = run_dir.name
    conn = sqlite3.connect(args.db)

    succ  = 0
    # 正式成功類
    succ += mark_from_dir(conn, run_dir, run_ts, "tickets",       "CreateTicket", "succeeded", {".json"}, args.verbose)
    succ += mark_from_dir(conn, run_dir, run_ts, "diffs",         "GenerateDiff", "succeeded", {".json"}, args.verbose)
    succ += mark_from_dir(conn, run_dir, run_ts, "quotes",        "GenerateQuote","succeeded", {".html",".pdf"}, args.verbose)
    succ += mark_from_dir(conn, run_dir, run_ts, "faq_replies",   "FAQReply",     "succeeded", {".txt",".md"}, args.verbose)
    # SendEmail：兩段式
    succ += mark_from_dir(conn, run_dir, run_ts, "email_sent",    "SendEmail",    "succeeded", {".eml"}, args.verbose)
    # 沒寄出的 outbox → 降級（保留）
    succ += mark_from_dir(conn, run_dir, run_ts, "email_outbox",  "SendEmail",    "downgraded", {".txt"}, args.verbose)

    print(f"[OK] backfill done for run {run_ts} → succeeded/updated={succ}")
    conn.close()

if __name__=="__main__":
    main()
