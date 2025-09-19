#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/rpa/quotation.py
# 模組用途
#   產生報價單/回覆，透過 utils/pdf_safe 安全輸出檔案。
from __future__ import annotations

from pathlib import Path
from typing import Any

from smart_mail_agent.utils.logger import get_logger
from smart_mail_agent.utils.pdf_safe import write_pdf_or_txt

log = get_logger("RPA/Quotation")


def render_quote(out_dir: Path, payload: dict[str, Any]) -> str:
    """參數: out_dir/payload；回傳: 檔案路徑。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    text = f"Quote for {payload.get('customer', 'N/A')}\nItems: {payload.get('items', [])}\n"
    out = out_dir / "quote.pdf"
    real = write_pdf_or_txt(str(out), text)
    log.info("[RPA/Quotation] 產生報價: %s", real)
    return real
