#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/cli/e2e.py
# 模組用途
#   解析參數 --eml-dir / --out-root，呼叫 run_action_handler.run_e2e_mail，輸出 LATEST_SUMMARY.md。
from __future__ import annotations

import argparse
from pathlib import Path

from smart_mail_agent.pipeline.run_action_handler import run_e2e_mail


def main() -> None:
    """參數: 由命令列取得；回傳: 無（檔案輸出在 out-root）。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--eml-dir", required=True)
    ap.add_argument("--out-root", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = run_e2e_mail(Path(args.eml_dir), out_dir)
    (out_dir / "LATEST_SUMMARY.md").write_text(summary, encoding="utf-8")


if __name__ == "__main__":
    main()
