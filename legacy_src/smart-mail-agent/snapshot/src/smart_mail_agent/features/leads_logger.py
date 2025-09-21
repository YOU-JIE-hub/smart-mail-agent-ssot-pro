#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from smart_mail_agent.utils.logger import logger

# 檔案位置：src/modules/leads_logger.py
# 模組用途：記錄潛在客戶 leads 資訊至 leads.db，供日後分析與轉換率追蹤


DB_PATH = Path("data/leads.db")
TABLE_NAME = "leads"


def ensure_db() -> None:
    """
    確保 leads 資料表存在，如無則自動建立。

    表格欄位：
        - id: 自動編號主鍵
        - email: 客戶信箱（必填）
        - company: 公司名稱（選填）
        - package: 詢問的方案名稱
        - created_at: UTC 時間戳記
        - source: 資料來源（如 email / web）
        - pdf_path: 報價單 PDF 檔案路徑
    """
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    company TEXT,
                    package TEXT,
                    created_at TEXT,
                    source TEXT,
                    pdf_path TEXT
                )
            """
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"[leads_logger] 建立資料表失敗：{e}")


def log_lead(
    email: str,
    package: str,
    pdf_path: str = "",
    company: str = "",
    source: str = "email",
) -> None:
    """
    寫入一筆 leads 記錄至 SQLite。

    參數:
        email (str): 客戶信箱（必填）
        package (str): 詢問的方案名稱
        pdf_path (str): 附檔報價單 PDF 路徑（可選）
        company (str): 公司名稱（可選）
        source (str): 資料來源（預設為 'email'）
    """
    try:
        ensure_db()
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                INSERT INTO {TABLE_NAME} (email, company, package, created_at, source, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (email, company, package, now, source, pdf_path),
            )
            conn.commit()
        logger.info(f"[leads_logger] 已記錄 leads：{email} / {package}")
    except Exception as e:
        logger.warning(f"[leads_logger] 寫入 leads 失敗：{e}")
