#!/usr/bin/env python3
# 檔案位置：scripts/run_spam_train.py
# 用途：訓練垃圾信規則模型 + 輸出驗證指標與最佳閾值
from smart_mail_agent.spam.train.rule_trainer import train
import argparse
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--val", required=True)
    ap.add_argument("--rules", default=".sma_tools/spam_rules.yml")
    ap.add_argument("--out", default="artifacts")
    args = ap.parse_args()
    train(args.train, args.val, args.rules, args.out)
