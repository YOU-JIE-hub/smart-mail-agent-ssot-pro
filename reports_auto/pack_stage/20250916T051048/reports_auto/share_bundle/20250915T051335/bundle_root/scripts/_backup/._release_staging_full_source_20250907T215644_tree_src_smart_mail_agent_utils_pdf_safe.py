#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/utils/pdf_safe.py
# 模組用途
#   安全地輸出 PDF 或純文字；無字型/無 reportlab 時自動降級為 .txt。
from __future__ import annotations

from pathlib import Path


def write_pdf_or_txt(out_path: str, text: str, font_path: str | None = None) -> str:
    """參數: out_path/text/font_path；回傳: 實際輸出的檔案路徑。"""
    out = Path(out_path)
    use_pdf = False
    try:
        from reportlab.pdfbase import pdfmetrics  # type: ignore
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore

        use_pdf = out.suffix.lower() == ".pdf" and font_path and Path(font_path).is_file()
    except Exception:
        use_pdf = False

    if not use_pdf:
        out = out.with_suffix(".txt")
        out.write_text(text, encoding="utf-8")
        return str(out)

    c = canvas.Canvas(str(out))
    try:
        pdfmetrics.registerFont(TTFont("SMAFont", str(font_path)))
        c.setFont("SMAFont", 12)
    except Exception:
        pass
    y = 800
    for line in text.splitlines():
        c.drawString(36, y, line)
        y -= 16
        if y < 36:
            c.showPage()
            y = 800
    c.save()
    return str(out)
