#!/usr/bin/env python3
from __future__ import annotations

import sqlite3

from smart_mail_agent.utils.logger import logger

# 檔案位置：src/utils/db_tools.py
# 模組用途：用於查詢 SQLite 使用者資料表（get by email / get all）


def get_user_by_email(db_path: str, email: str) -> dict | None:
    """
    根據 email 查詢單一使用者資料

    :param db_path: 資料庫檔案路徑
    :param email: 欲查詢的 Email
    :return: dict 或 None，查無資料時回傳 None
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, email, name, phone, address
            FROM users
            WHERE email = ?
        """,
            (email,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            logger.info(f"[DB] 查詢成功：{email}")
            return {
                "id": row[0],
                "email": row[1],
                "name": row[2],
                "phone": row[3],
                "address": row[4],
            }
        else:
            logger.warning(f"[DB] 查無資料：{email}")
            return None

    except Exception as e:
        logger.error(f"[DB] 查詢使用者失敗：{e}")
        return None


def get_all_users(db_path: str) -> list[dict]:
    """
    查詢所有使用者資料

    :param db_path: 資料庫檔案路徑
    :return: list of dicts，包含所有使用者欄位
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, name, phone, address FROM users")
        rows = cursor.fetchall()
        conn.close()

        logger.info(f"[DB] 成功查詢所有使用者，共 {len(rows)} 筆")
        return [
            {
                "id": row[0],
                "email": row[1],
                "name": row[2],
                "phone": row[3],
                "address": row[4],
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"[DB] 查詢所有使用者失敗：{e}")
        return []


# CLI 測試入口
if __name__ == "__main__":
    db_path = "data/users.db"

    print("【查詢全部使用者】")
    all_users = get_all_users(db_path)
    for user in all_users:
        print(user)

    print("\n【查詢單一使用者】")
    user = get_user_by_email(db_path, "test@example.com")
    print(user or "找不到對應使用者")
