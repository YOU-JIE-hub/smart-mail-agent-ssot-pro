#!/usr/bin/env python3
# 檔案位置：scripts/run_spam_eval.py
# 用途：評測（可選 LLM 權重）
from smart_mail_agent.spam.train.evaluator import evaluate
import argparse
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--rules", default=".sma_tools/spam_rules.yml")
    ap.add_argument("--model", default="artifacts/spam_rules_lr.pkl")
    ap.add_argument("--thresholds", default="artifacts/spam_thresholds.json")
    ap.add_argument("--w-rule", type=float, default=1.0)
    ap.add_argument("--w-llm", type=float, default=0.0)
    ap.add_argument("--out", default="reports_auto/spam_eval.txt")
    args = ap.parse_args()
    evaluate(args.data, args.rules, args.model, args.thresholds, args.w_rule, args.w_llm, args.out)
