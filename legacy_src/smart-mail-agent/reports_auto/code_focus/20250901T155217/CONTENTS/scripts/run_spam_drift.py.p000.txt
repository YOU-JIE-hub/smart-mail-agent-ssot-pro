#!/usr/bin/env python3
# 檔案位置：scripts/run_spam_drift.py
# 用途：生成漂移報告
from smart_mail_agent.spam.train.drift_report import drift_report
import argparse
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="未標註或新批次 JSONL")
    ap.add_argument("--rules", default=".sma_tools/spam_rules.yml")
    ap.add_argument("--vocab", default="artifacts/spam_vocab.json")
    ap.add_argument("--out", default="reports_auto")
    args = ap.parse_args()
    drift_report(args.data, args.rules, args.vocab, args.out)
