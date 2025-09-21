from __future__ import annotations

import argparse
import json
import os
import sqlite3
import traceback
from pathlib import Path

from smart_mail_agent.actions.executors import execute_action
from smart_mail_agent.actions.types import ActionContext


def latest_out_root() -> Path:
    base = Path("reports_auto/e2e_mail")
    link = base / "LATEST"
    return link.resolve() if link.exists() else base


def run(once: bool = False) -> int:
    db = Path(os.environ.get("SMA_DB_PATH", "reports_auto/audit.sqlite3"))
    out_root = Path(os.environ.get("SMA_OUT_ROOT", latest_out_root()))
    offline = os.environ.get("OFFLINE", "0") == "1"
    env = dict(os.environ)
    ctx = ActionContext(db_path=db, out_root=out_root, offline=offline, env=env)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.execute("SELECT * FROM actions WHERE status='queued' ORDER BY ts ASC")
    rows = cur.fetchall()
    conn.close()
    ok = 0
    err = 0
    for r in rows:
        name = r["action"]
        key = r["idempotency_key"]
        payload = json.loads(r["payload"] or "{}")
        try:
            execute_action(name, payload, ctx, key)
            ok += 1
        except Exception as e:
            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE actions SET status='error', payload=? WHERE idempotency_key=?",
                (json.dumps({"reason": str(e), "traceback": traceback.format_exc()}), key),
            )
            conn.commit()
            conn.close()
            err += 1
        if once:
            break
    print(json.dumps({"queued": len(rows), "ok": ok, "error": err}))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    raise SystemExit(run(once=args.once))
