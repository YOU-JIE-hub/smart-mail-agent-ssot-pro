#!/usr/bin/env python3
import sys, os
from smart_mail_agent.pipeline.run_action_handler import run_e2e_mail

def main():
    if len(sys.argv) < 3:
        in_dir = "data/demo_eml"
        out_dir = "reports_auto/e2e_mail"
    else:
        in_dir = sys.argv[1]; out_dir = sys.argv[2]
    db = os.environ.get("SMA_DB_PATH","db/sma.sqlite")
    nd = "reports_auto/logs/pipeline.ndjson"
    run_e2e_mail(in_dir, out_dir, db_path=db, ndjson_path=nd)

if __name__ == "__main__":
    main()
