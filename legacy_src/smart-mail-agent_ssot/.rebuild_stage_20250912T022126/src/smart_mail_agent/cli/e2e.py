from __future__ import annotations

import argparse
from pathlib import Path
import sys

from smart_mail_agent.observability.ndjson_v1 import NDJSONLogger
from smart_mail_agent.pipeline.run_action_handler import run_e2e_mail

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="e2e.py")
    p.add_argument("--eml-dir", dest="eml_dir", help="Directory containing .eml files")
    p.add_argument("--out-root", dest="out_root", default=".", help="Output root (or target run dir)")
    p.add_argument("--db-path", dest="db_path", default="db/sma.sqlite", help="Path to sqlite DB")
    p.add_argument("--ndjson", dest="ndjson", default=None, help="Events ndjson path")
    # 兼容舊用法：把 eml 目錄當成位置參數給進來
    p.add_argument("eml_dir_pos", nargs="?", help="(optional) positional eml dir")
    return p.parse_args()

def main() -> None:
    args = parse_args()
    eml_dir = args.eml_dir or args.eml_dir_pos
    if not eml_dir:
        print("usage: e2e.py --eml-dir <DIR> [--out-root OUT] [--db-path DB] [--ndjson FILE]", file=sys.stderr)
        sys.exit(2)

    in_dir = Path(eml_dir)
    if not in_dir.exists():
        print(f"[FATAL] not found: {in_dir}", file=sys.stderr)
        sys.exit(2)

    out_dir = Path(args.out_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    ndjson_path = args.ndjson or str(Path("reports_auto/events") / (out_dir.name + ".ndjson"))

    logger = NDJSONLogger(ndjson_path)
    logger.write(action="e2e_start", result="ok")

    try:
        # 委派到你原本的執行器；不改任何既有行為
        run_e2e_mail(str(in_dir), str(out_dir), db_path=args.db_path, ndjson_path=ndjson_path)
        logger.write(action="e2e_done", result="ok")
    except Exception as e:
        logger.write_exception(action="e2e_fail", exc=e)
        raise

if __name__ == "__main__":
    main()
