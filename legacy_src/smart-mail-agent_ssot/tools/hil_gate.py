from __future__ import annotations
from pathlib import Path
import json, os, time, sys
from smart_mail_agent.observability.ndjson_v1 import NDJSONLogger

"""
HIL gate：當 SMA_HIL_MODE=on 時，
- 若 outbox/*.txt 有對應 *.approved 檔才允許寄送；
- 否則移到 rpa_out/email_blocked/ 並在 NDJSON 記錄 hil_blocked。
"""
def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--ndjson", required=False, default=None)
    args=ap.parse_args()
    rd=Path(args.run_dir)
    outbox=rd/"rpa_out"/"email_outbox"
    blocked=rd/"rpa_out"/"email_blocked"
    blocked.mkdir(parents=True, exist_ok=True)
    ndjson=args.ndjson or f"reports_auto/events/{rd.name}.ndjson"
    logger=NDJSONLogger(ndjson)

    if os.getenv("SMA_HIL_MODE","off")!="on":
        logger.write(action="hil_bypass", result="ok")
        return

    moved=0
    for txt in sorted(outbox.glob("*.txt")):
        appr=txt.with_suffix(".approved")
        if not appr.exists():
            dest=blocked/txt.name
            txt.replace(dest)
            logger.write(action="hil_blocked", result="blocked", idem=txt.stem)
            moved+=1
    logger.write(action="hil_done", result="ok", moved=moved)
if __name__=="__main__":
    main()
