import argparse
import json
import os

from smart_mail_agent.ingest.eml_dir import load_dir
from smart_mail_agent.ingest.imap_pull import pull_imap
from smart_mail_agent.utils.config import paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None)
    ap.add_argument("--imap", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    P = paths()
    items = []
    if args.dir:
        items = load_dir(args.dir)
    elif args.imap:
        cfg = {
            "host": os.getenv("IMAP_HOST"),
            "port": os.getenv("IMAP_PORT"),
            "user": os.getenv("IMAP_USER"),
            "pass": os.getenv("IMAP_PASS"),
            "ssl": os.getenv("IMAP_SSL", "1") == "1",
            "mailbox": os.getenv("IMAP_MAILBOX", "INBOX"),
        }
        items = pull_imap(cfg)
    else:
        items = load_dir("samples/inbox")
    out = P.status / ("INBOX_latest.jsonl" if not args.out else args.out)
    with open(out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(json.dumps({"ok": True, "count": len(items), "out": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
