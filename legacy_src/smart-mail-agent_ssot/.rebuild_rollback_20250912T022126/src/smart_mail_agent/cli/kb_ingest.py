from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from smart_mail_agent.rag.provider import ensure_schema, ingest_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kb_dir", nargs="?", default=os.environ.get("KB_DIR", "kb_docs"))
    args = ap.parse_args()
    ensure_schema()
    cnt = ingest_dir(Path(args.kb_dir))
    print(json.dumps({"ingested": cnt, "kb_dir": str(Path(args.kb_dir).resolve())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
