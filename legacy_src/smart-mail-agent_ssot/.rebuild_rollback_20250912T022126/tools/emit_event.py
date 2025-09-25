#!/usr/bin/env python3
import argparse, json, os, time
from pathlib import Path
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ndjson", default="reports_auto/logs/pipeline.ndjson")
    ap.add_argument("--run-ts", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--case-id", default="")
    ap.add_argument("--action", default="")
    ap.add_argument("--status", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--duration-ms", type=int, default=0)
    a=ap.parse_args()
    Path(os.path.dirname(a.ndjson)).mkdir(parents=True, exist_ok=True)
    evt = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "run_ts": a.run_ts,
        "stage": a.stage,
        "case_id": a.case_id or None,
        "action": a.action or None,
        "status": a.status or None,
        "reason": a.reason or None,
        "duration_ms": a.duration_ms
    }
    with open(a.ndjson, "a", encoding="utf-8") as w: w.write(json.dumps(evt, ensure_ascii=False)+"\n")
    print(f"[OK] event written: {evt}")
if __name__=="__main__": main()
