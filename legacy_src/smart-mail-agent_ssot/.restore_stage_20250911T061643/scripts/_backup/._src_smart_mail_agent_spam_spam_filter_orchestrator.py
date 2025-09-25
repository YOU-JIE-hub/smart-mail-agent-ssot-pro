#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/spam/spam_filter_orchestrator.py
# 模組用途
#   規則分數 + ML 分數的綜合判斷與 CLI。
from __future__ import annotations

import argparse
from pathlib import Path

from .ens import SpamEnsemble


def predict_score(text: str, sender: str | None = None) -> float:
    """參數: text/sender；回傳: spam 機率（供外部使用）。"""
    root = Path(__file__).resolve().parents[3]
    return float(SpamEnsemble(root).predict_detail(text)["proba"])


def is_spam(text: str, sender: str | None = None, threshold: float = 0.6) -> bool:
    """參數: text/sender/threshold；回傳: True=垃圾。"""
    root = Path(__file__).resolve().parents[3]
    d = SpamEnsemble(root).predict_detail(text)
    return bool(d["ens"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--sender", default=None)
    ap.add_argument("--threshold", type=float, default=0.6)
    a = ap.parse_args()
    print("1" if is_spam(a.text, a.sender, a.threshold) else "0")


if __name__ == "__main__":
    main()
