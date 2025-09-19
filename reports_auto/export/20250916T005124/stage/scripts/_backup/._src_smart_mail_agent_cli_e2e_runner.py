from __future__ import annotations
import os, time, argparse
from smart_mail_agent.pipeline.run_action_handler import run_e2e_mail

def main():
    ap = argparse.ArgumentParser(description="E2E mail runner (compat)")
    ap.add_argument("--input-dir","--eml-dir", dest="input_dir")
    ap.add_argument("--out-dir","--out-root", dest="out_dir")
    ap.add_argument("--db-path", default=os.environ.get("SMA_DB_PATH","db/sma.sqlite"))
    ap.add_argument("--ndjson-path", default="reports_auto/logs/pipeline.ndjson")
    ap.add_argument("pos_in", nargs="?")
    ap.add_argument("pos_out", nargs="?")
    args = ap.parse_args()

    in_dir = args.input_dir or args.pos_in or "data/demo_eml"
    out_dir = args.out_dir or args.pos_out or f"reports_auto/e2e_mail/{time.strftime('%Y%m%dT%H%M%S')}"
    run_e2e_mail(in_dir, out_dir, db_path=args.db_path, ndjson_path=args.ndjson_path)

if __name__ == "__main__":
    main()
