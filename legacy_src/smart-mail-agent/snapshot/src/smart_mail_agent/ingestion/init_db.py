#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path

from smart_mail_agent.utils.logger import logger

# 檔案位置：src/init_db.py
# 模組用途：初始化專案所需的所有 SQLite 資料庫與資料表


# ===== 資料夾與路徑設定 =====
DATA_DIR = Path("data")
DB_DIR = DATA_DIR / "db"


# ===== 公用工具 =====
def ensure_dir(path: Path) -> None:
    """
    確保指定資料夾存在，若無則建立

    參數:
        path (Path): 資料夾路徑
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error("無法建立資料夾 %s：%s", path, e)


# ===== 初始化 users.db =====
def init_users_db():
    """
    建立使用者資料表 users 與異動記錄表 diff_log
    """
    ensure_dir(DATA_DIR)
    db_path = DATA_DIR / "users.db"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT,
                phone TEXT,
                address TEXT
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS diff_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                欄位 TEXT,
                原值 TEXT,
                新值 TEXT,
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()
        logger.info("[DB] users.db 初始化完成")

    except Exception as e:
        logger.error("[DB] users.db 初始化失敗：%s", e)


# ===== 初始化 tickets.db =====
def init_tickets_db():
    """
    建立技術支援工單表 support_tickets
    """
    ensure_dir(DATA_DIR)
    db_path = DATA_DIR / "tickets.db"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                sender TEXT,
                category TEXT,
                confidence REAL,
                created_at TEXT,
                updated_at TEXT,
                status TEXT,
                priority TEXT
            )
        """
        )

        conn.commit()
        conn.close()
        logger.info("[DB] tickets.db 初始化完成")

    except Exception as e:
        logger.error("[DB] tickets.db 初始化失敗：%s", e)


# ===== 初始化 emails_log.db =====
def init_emails_log_db():
    """
    建立郵件分類紀錄表 emails_log
    """
    ensure_dir(DATA_DIR)
    db_path = DATA_DIR / "emails_log.db"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS emails_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT,
                content TEXT,
                summary TEXT,
                predicted_label TEXT,
                confidence REAL,
                action TEXT,
                error TEXT,
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()
        logger.info("[DB] emails_log.db 初始化完成")

    except Exception as e:
        logger.error("[DB] emails_log.db 初始化失敗：%s", e)


# ===== 初始化 processed_mails.db =====
def init_processed_mails_db():
    """
    建立已處理信件 UID 記錄表 processed_mails
    """
    ensure_dir(DB_DIR)
    db_path = DB_DIR / "processed_mails.db"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_mails (
                uid TEXT PRIMARY KEY,
                subject TEXT,
                sender TEXT
            )
        """
        )

        conn.commit()
        conn.close()
        logger.info("[DB] processed_mails.db 初始化完成")

    except Exception as e:
        logger.error("[DB] processed_mails.db 初始化失敗：%s", e)


# ===== 主執行流程 =====
def main():
    logger.info("[DB] 開始初始化所有資料庫...")
    init_users_db()
    init_tickets_db()
    init_emails_log_db()
    init_processed_mails_db()
    logger.info("[DB] 所有資料庫初始化完成")


if __name__ == "__main__":
    main()
