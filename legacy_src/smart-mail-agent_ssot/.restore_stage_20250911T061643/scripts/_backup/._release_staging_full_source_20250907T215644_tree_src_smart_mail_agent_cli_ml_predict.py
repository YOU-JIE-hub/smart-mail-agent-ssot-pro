from __future__ import annotations

import argparse
import json
import sys

from smart_mail_agent.ml.loader import extract_kie, predict_intent, predict_spam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=["spam", "intent", "kie"])
    ap.add_argument("--text", default="")
    args = ap.parse_args()
    text = args.text or sys.stdin.read()
    if args.task == "spam":
        out = predict_spam(text)
    elif args.task == "intent":
        out = predict_intent(text)
    else:
        out = extract_kie(text)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
