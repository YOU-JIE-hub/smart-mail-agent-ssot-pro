#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/cli/spamcheck.py
# 模組用途
#   以 JSON 印出垃圾判定。
from __future__ import annotations

import argparse
import json
from pathlib import Path

from smart_mail_agent.spam.ens import SpamEnsemble


def main() -> None:
    """參數: --text 或 --file；回傳: 無（stdout 輸出 JSON）。"""
    ap = argparse.ArgumentParser("sma-spamcheck")
    ap.add_argument("--text")
    ap.add_argument("--file")
    a = ap.parse_args()
    if not (a.text or a.file):
        ap.error("must provide --text or --file")
    text = a.text or Path(a.file).read_text(encoding="utf-8", errors="ignore")
    print(
        json.dumps(SpamEnsemble(Path(__file__).resolve().parents[3]).predict_detail(text), ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
