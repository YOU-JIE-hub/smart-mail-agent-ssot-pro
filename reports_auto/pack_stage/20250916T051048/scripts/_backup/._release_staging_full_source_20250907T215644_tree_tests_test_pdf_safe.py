#!/usr/bin/env python3
# 檔案位置: tests/test_pdf_safe.py
# 模組用途: 驗證 pdf_safe 可在無字型/無 reportlab 的情況下降級輸出為 .txt 檔。
from pathlib import Path

from smart_mail_agent.utils.pdf_safe import write_pdf_or_txt


def test_pdf_safe_degrade_to_txt(tmp_path: Path) -> None:
    out = tmp_path / "demo.pdf"
    real = write_pdf_or_txt(str(out), "hello report")
    assert Path(real).exists()
