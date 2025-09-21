from __future__ import annotations

import os

#!/usr/bin/env python3
# 檔案位置：src/utils/pdf_generator.py
# 模組用途：產出異動紀錄 PDF，支援中文顯示與系統字型錯誤備援處理
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from smart_mail_agent.utils.logger import logger

load_dotenv()

# 讀取字型路徑
FONT_PATH = os.getenv("QUOTE_FONT_PATH", "/usr/share/fonts/truetype/noto/NotoSansTC-Regular.otf")

try:
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(f"找不到字型檔案：{FONT_PATH}")
    pdfmetrics.registerFont(TTFont("NotoSansTC", FONT_PATH))
    FONT_NAME = "NotoSansTC"
    logger.info("[PDFGenerator] 載入字型成功：%s", FONT_PATH)
except Exception as e:
    FONT_NAME = "Helvetica"
    logger.warning("[PDFGenerator] 使用預設字型 Helvetica，原因：%s", str(e))


def generate_info_change_pdf(info_dict: dict, save_path: str):
    """
    根據使用者異動資訊產出正式 PDF 檔案

    :param info_dict: 異動欄位與新值的 dict
    :param save_path: 儲存的 PDF 完整路徑
    """
    try:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(save_path, pagesize=A4)
        width, height = A4

        margin = 50
        line_height = 24
        y = height - margin

        # 標題
        c.setFont(FONT_NAME, 18)
        c.drawString(margin, y, "客戶資料異動紀錄")
        y -= line_height * 2

        # 系統說明
        c.setFont(FONT_NAME, 12)
        c.drawString(
            margin,
            y,
            "以下為客戶主動申請之資料異動內容，已由 Smart-Mail-Agent 系統自動紀錄：",
        )
        y -= line_height * 2

        # 異動欄位列出
        for key, value in info_dict.items():
            if value.strip():
                c.drawString(margin, y, f"■ {key.strip()}：{value.strip()}")
                y -= line_height

        y -= line_height

        # 系統資訊
        c.setFont(FONT_NAME, 11)
        c.drawString(margin, y, f"異動提交時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        y -= line_height
        c.drawString(margin, y, "系統產出：Smart-Mail-Agent")
        y -= line_height * 2

        # 備註
        c.setFont(FONT_NAME, 10)
        c.drawString(margin, y, "※ 此紀錄由系統自動產生，若資訊有誤請回覆本信通知更正。")

        c.save()
        logger.info("[PDFGenerator] PDF 已產出：%s", save_path)

    except Exception as e:
        logger.error("[PDFGenerator] PDF 產出失敗：%s", str(e))
