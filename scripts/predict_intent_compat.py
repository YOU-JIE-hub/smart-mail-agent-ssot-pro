#!/usr/bin/env python
import os, json, argparse
from sma.common.intent_compat import load_pipeline, predict_intent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("INTENT_PKL",""), help="path to intent_pro_cal.pkl")
    ap.add_argument("--text", required=True)
    args = ap.parse_args()
    if not args.model:
        raise SystemExit("[FATAL] set --model or INTENT_PKL")
    load_pipeline(args.model)
    out = predict_intent(args.text)
    print(json.dumps({"task":"intent","text":args.text, **out}, ensure_ascii=False))
if __name__ == "__main__":
    main()
