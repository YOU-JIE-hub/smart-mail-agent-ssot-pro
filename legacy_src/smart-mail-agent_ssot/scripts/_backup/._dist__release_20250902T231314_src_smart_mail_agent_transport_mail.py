#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/transport/mail.py
# 模組用途
#   file-transport 與 SMTP 介面（預設 file-transport）。
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def send_file_transport(out_dir: Path, rec: dict[str, Any]) -> Path:
    """參數: out_dir/rec；回傳: 產生的檔案路徑。"""
    out = out_dir / "rpa_out" / "email_outbox"
    out.mkdir(parents=True, exist_ok=True)
    fp = out / f"{rec['payload']['mail_id']}.eml.json"
    fp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    return fp


def send_smtp(rec: dict[str, Any]) -> None:
    """參數: rec；回傳: 無（未設定環境變數時拋出錯誤）。"""
    if not os.environ.get("SMTP_HOST"):
        raise RuntimeError("SMTP_* not configured; use file-transport instead.")
