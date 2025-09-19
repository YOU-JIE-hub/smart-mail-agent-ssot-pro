#!/usr/bin/env python3
import argparse, json, os, sqlite3, sys, time
from pathlib import Path

NOW = lambda: time.strftime("%Y-%m-%dT%H:%M:%S")

# ---------- DB helpers ----------
def cols(conn, table):
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table});")}
    except sqlite3.Error:
        return set()

def approvals_pending(conn, run_ts, case_id, action_type):
    # approvals 不一定存在；存在才檢查
    t = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='approvals'").fetchone()
    if not t: return False
    row = conn.execute("""
      SELECT status FROM approvals
      WHERE run_ts=? AND case_id=? AND (action_type=? OR action_type IS NULL)
      ORDER BY created_at DESC LIMIT 1
    """, (run_ts, case_id, action_type)).fetchone()
    return (row and row[0] == 'pending')

def upsert_action(conn, base, *, status=None, payload_json=None, started=False, ended=False):
    """
    base: {case_id, type, idempotency_key, run_ts}
    對齊舊表：type→(type|action_type|action), payload_json→(payload_json|payload_ref)
    僅當欄位存在時才寫（包含 updated_at/started_at/ended_at/run_ts/created_at）
    """
    c = cols(conn, "actions")
    if not c:
        print("[FATAL] actions table missing", file=sys.stderr); sys.exit(5)

    type_col    = "type" if "type" in c else ("action_type" if "action_type" in c else "action")
    payload_col = "payload_json" if "payload_json" in c else ("payload_ref" if "payload_ref" in c else None)

    has_started   = "started_at"  in c
    has_ended     = "ended_at"    in c
    has_run_ts    = "run_ts"      in c
    has_updated   = "updated_at"  in c
    has_created   = "created_at"  in c

    cur = conn.cursor()
    row = cur.execute("SELECT status FROM actions WHERE idempotency_key=?", (base["idempotency_key"],)).fetchone()

    if row is None:
        cols_ins = ["case_id", type_col, "status", "idempotency_key"]
        vals_ins = [base["case_id"], base["type"], status or "planned", base["idempotency_key"]]
        if payload_col and payload_json is not None:
            cols_ins.append(payload_col); vals_ins.append(payload_json)
        if has_run_ts:
            cols_ins.append("run_ts"); vals_ins.append(base["run_ts"])
        if has_created:
            cols_ins.append("created_at"); vals_ins.append(NOW())
        cur.execute(f"INSERT INTO actions ({', '.join(cols_ins)}) VALUES ({', '.join('?'*len(vals_ins))});", vals_ins)
    else:
        sets, vals = [], []
        if status is not None:
            sets.append("status=?"); vals.append(status)
        if payload_col and payload_json is not None:
            sets.append(f"{payload_col}=?"); vals.append(payload_json)
        if started and has_started:
            sets.append("started_at=?"); vals.append(NOW())
        if ended and has_ended:
            sets.append("ended_at=?"); vals.append(NOW())
        if has_updated:
            sets.append("updated_at=?"); vals.append(NOW())
        # run_ts 只在 insert 時寫；update 不動
        sets_str = ", ".join(sets) if sets else "status=status"
        vals.append(base["idempotency_key"])
        cur.execute(f"UPDATE actions SET {sets_str} WHERE idempotency_key=?;", vals)
    conn.commit()

# ---------- executors (offline-safe) ----------
def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)

def exec_create_ticket(run_dir: Path, case_id: str):
    out = run_dir / "rpa_out" / "tickets" / f"{case_id}.json"
    payload = {"case_id": case_id, "ticket_id": f"TCK-{case_id[:8]}", "created_at": NOW()}
    write_text(out, json.dumps(payload, ensure_ascii=False, indent=2))
    return str(out)

def exec_generate_quote(run_dir: Path, case_id: str):
    out = run_dir / "rpa_out" / "quotes" / f"{case_id}.html"
    html = f"<html><body><h3>Quote for {case_id}</h3><p>Total: $1234</p></body></html>"
    write_text(out, html)
    return str(out)

def exec_generate_diff(run_dir: Path, case_id: str):
    out = run_dir / "rpa_out" / "diffs" / f"{case_id}.json"
    diff = {"case_id": case_id, "changes": [{"field":"address","old":"A","new":"B"}], "engine":"regex"}
    write_text(out, json.dumps(diff, ensure_ascii=False, indent=2))
    return str(out)

def exec_faq_reply(run_dir: Path, case_id: str):
    out = run_dir / "rpa_out" / "faq_replies" / f"{case_id}.txt"
    body = f"[FAQReply] Case {case_id}\n\nAnswer:\n- Please see our FAQ..."
    write_text(out, body)
    return str(out)

def exec_send_email(run_dir: Path, case_id: str):
    mode = os.getenv("SMA_SMTP_MODE", "outbox").lower()
    out = run_dir / "rpa_out" / "email_outbox" / f"{case_id}.txt"
    body = f"TO: customer@example.com\nSUBJECT: Re: Case {case_id}\n\nThis is a simulated email."
    write_text(out, body)
    if mode != "smtp":
        return "downgraded", "outbox", str(out)  # 記錄降級原因
    return "succeeded", "", str(out)

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_ts = run_dir.name
    plan_path = run_dir / "actions_plan.ndjson"
    if not plan_path.exists():
        print(f"[FATAL] not found: {plan_path}", file=sys.stderr); sys.exit(3)

    conn = sqlite3.connect(args.db)

    with open(plan_path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln: continue
            try:
                it = json.loads(ln)
            except Exception:
                continue

            case_id = it.get("case_id") or it.get("id")
            act = it.get("type") or it.get("action_type") or it.get("action")
            if not case_id or not act: continue

            idem = f"{run_ts}:{case_id}:{act}"
            base = {"case_id": case_id, "type": act, "idempotency_key": idem, "run_ts": run_ts}

            # HIL gate
            if approvals_pending(conn, run_ts, case_id, act):
                upsert_action(conn, base, status="skipped_by_hil")
                continue

            # running
            upsert_action(conn, base, status="running", started=True)

            # execute
            try:
                payload_path = None
                if act in ("CreateTicket","create_ticket"):
                    payload_path = exec_create_ticket(run_dir, case_id)
                    upsert_action(conn, base, status="succeeded", payload_json=payload_path, ended=True)
                elif act in ("GenerateQuote","make_quote","generate_quote"):
                    payload_path = exec_generate_quote(run_dir, case_id)
                    upsert_action(conn, base, status="succeeded", payload_json=payload_path, ended=True)
                elif act in ("GenerateDiff","generate_diff"):
                    payload_path = exec_generate_diff(run_dir, case_id)
                    upsert_action(conn, base, status="succeeded", payload_json=payload_path, ended=True)
                elif act in ("FAQReply","send_faq_reply","faq_answer"):
                    payload_path = exec_faq_reply(run_dir, case_id)
                    upsert_action(conn, base, status="succeeded", payload_json=payload_path, ended=True)
                elif act in ("SendEmail","send_email"):
                    final, reason, payload_path = exec_send_email(run_dir, case_id)
                    if final == "downgraded":
                        # 降級：仍視為完成，但狀態寫 downgraded
                        upsert_action(conn, base, status="downgraded", payload_json=payload_path, ended=True)
                    else:
                        upsert_action(conn, base, status="succeeded", payload_json=payload_path, ended=True)
                else:
                    # 未知動作：標記 failed
                    upsert_action(conn, base, status="failed", ended=True, payload_json=None)
            except Exception:
                upsert_action(conn, base, status="failed", ended=True)

    conn.close()
    print(f"[OK] apply completed for run {run_ts}")

if __name__ == "__main__":
    main()
