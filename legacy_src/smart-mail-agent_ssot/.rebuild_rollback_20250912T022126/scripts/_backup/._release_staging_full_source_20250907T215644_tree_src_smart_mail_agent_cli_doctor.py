import glob
import json
import os
import pathlib
import platform
import sqlite3
import time

from smart_mail_agent.utils.config import paths


def main():
    P = paths()
    ts = time.strftime("%Y%m%dT%H%M%S")
    tri = P.reports / "triage" / ts
    tri.mkdir(parents=True, exist_ok=True)
    info = {
        "ts": ts,
        "python": platform.python_version(),
        "cwd": str(pathlib.Path(".").resolve()),
        "env": {k: v for k, v in os.environ.items() if k.startswith(("SMA_", "OPENAI", "IMAP", "SMTP", "OFFLINE"))},
    }
    (tri / "env.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    for pat in [
        "reports_auto/logs/*.log",
        "reports_auto/logs/*.jsonl",
        "reports_auto/status/*.json",
        "reports_auto/status/*.jsonl",
        "reports_auto/status/*.md",
    ]:
        for f in glob.glob(pat):
            try:
                dst = tri / pathlib.Path(f).name
                dst.write_bytes(pathlib.Path(f).read_bytes())
            except Exception:
                pass
    # DB quick stats
    db = os.getenv("SMA_DB_PATH", "reports_auto/sma.sqlite3")
    try:
        cx = sqlite3.connect(db)
        cnts = {}
        for table in ["actions", "answers", "quotes", "tickets", "alerts", "errors"]:
            try:
                n = cx.execute(f"SELECT COUNT(1) FROM {table}").fetchone()[0]
                cnts[table] = int(n)
            except Exception:
                pass
        (tri / "db_counts.json").write_text(json.dumps(cnts, ensure_ascii=False, indent=2), encoding="utf-8")
        cx.close()
    except Exception:
        pass
    print(json.dumps({"ok": True, "triage_dir": str(tri)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
