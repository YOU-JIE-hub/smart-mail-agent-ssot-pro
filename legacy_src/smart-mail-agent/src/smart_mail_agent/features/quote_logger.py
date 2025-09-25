from __future__ import annotations

import os

#!/usr/bin/env python3
# 檔案位置：src/modules/quote_logger.py
# 模組用途：將報價記錄寫入 SQLite，用於封存、銷售分析與發送狀態追蹤
import sqlite3
from datetime import datetime
from pathlib import Path

from smart_mail_agent.utils.logger import logger

# 預設資料庫與資料表名稱
DEFAULT_DB_PATH = "data/quote_log.db"
DEFAULT_TABLE = "quote_records"


def ensure_db_exists(db_path: str = DEFAULT_DB_PATH, table_name: str = DEFAULT_TABLE) -> None:
    """
    確保 SQLite 資料庫與表格存在，若無則建立

    參數:
        db_path (str): 資料庫路徑
        table_name (str): 資料表名稱
    """
    try:
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_name TEXT NOT NULL,
                    package TEXT NOT NULL,
                    pdf_path TEXT NOT NULL,
                    sent_status TEXT DEFAULT 'success',
                    created_at TEXT NOT NULL
                );
            """
            )
        logger.debug("[quote_logger] 資料表已確認存在：%s", table_name)
    except Exception as e:
        logger.error("[quote_logger] 建立資料表失敗：%s", str(e))
        raise


def log_quote(
    client_name: str,
    package: str,
    pdf_path: str,
    sent_status: str = "success",
    db_path: str = DEFAULT_DB_PATH,
    table_name: str = DEFAULT_TABLE,
) -> None:
    """
    寫入一筆報價紀錄資料

    參數:
        client_name (str): 客戶名稱或 Email
        package (str): 報價方案（基礎 / 專業 / 企業）
        pdf_path (str): 報價單 PDF 路徑
        sent_status (str): 寄送狀態（預設為 success）
        db_path (str): SQLite 資料庫路徑
        table_name (str): 資料表名稱
    """
    try:
        ensure_db_exists(db_path, table_name)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                f"""
                INSERT INTO {table_name} (client_name, package, pdf_path, sent_status, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (client_name, package, pdf_path, sent_status, now),
            )
        logger.info("[quote_logger] 報價記錄已寫入：%s / %s", client_name, package)
    except Exception as e:
        logger.error("[quote_logger] 寫入資料庫失敗：%s", str(e))
        raise


def get_latest_quote(
    db_path: str = DEFAULT_DB_PATH, table_name: str = DEFAULT_TABLE
) -> tuple[str, str, str] | None:
    """
    取得最新一筆報價記錄（供測試用）

    回傳:
        tuple(client_name, package, pdf_path) 或 None
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT client_name, package, pdf_path
                FROM {table_name}
                ORDER BY id DESC
                LIMIT 1
            """
            )
            return cursor.fetchone()
    except Exception as e:
        logger.error("[quote_logger] 查詢報價資料失敗：%s", str(e))
        return None
