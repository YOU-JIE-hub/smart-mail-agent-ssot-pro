#!/usr/bin/env python3
# 檔案位置：src/support_ticket.py
# 模組用途：技術支援工單管理（建立 / 查詢 / 更新），自動標定優先等級

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

from smart_mail_agent.utils.logger import logger

try:
    from smart_mail_agent.utils.priority_evaluator import evaluate_priority
except ImportError:

    def evaluate_priority(*args, **kwargs):
        logger.warning("未載入 priority_evaluator 模組，預設優先等級為 normal")
        return "normal"


DB_PATH = "data/tickets.db"
TABLE = "support_tickets"


def init_db():
    Path("data").mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
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


def create_ticket(subject, content, summary="", sender=None, category=None, confidence=None):
    init_db()
    subject = subject or "(未填寫)"
    content = content or ""
    summary = summary or ""
    sender = sender or "unknown"
    category = category or "未分類"
    confidence = float(confidence or 0)

    try:
        priority = evaluate_priority(subject, content, sender, category, confidence)
    except Exception as e:
        logger.warning("evaluate_priority 失敗，預設為 normal：%s", e)
        priority = "normal"

    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            f"""
            INSERT INTO {TABLE}
            (subject, content, summary, sender, category, confidence,
             created_at, updated_at, status, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                subject,
                content,
                summary,
                sender,
                category,
                confidence,
                now,
                now,
                "pending",
                priority,
            ),
        )
        conn.commit()
    logger.info("工單建立成功 [%s] 優先級：%s", subject, priority)


def list_tickets():
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            f"""
            SELECT id, subject, status, priority, created_at
            FROM {TABLE}
            ORDER BY id DESC
        """
        ).fetchall()

    if not rows:
        print("目前尚無工單紀錄")
        return

    print("\n=== 最新工單列表 ===")
    for row in rows:
        print(f"[#{row[0]}] [{row[2]}] [{row[3]}] {row[1]} @ {row[4]}")


def show_ticket(ticket_id: int):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(f"SELECT * FROM {TABLE} WHERE id=?", (ticket_id,)).fetchone()

    if not row:
        print(f"查無工單 ID={ticket_id}")
        return

    print(
        f"""
--- 工單詳細內容 ---
ID         : {row[0]}
主旨       : {row[1]}
內容       : {row[2]}
摘要       : {row[3]}
寄件者     : {row[4]}
分類       : {row[5]}
信心分數   : {row[6]:.2f}
建立時間   : {row[7]}
更新時間   : {row[8]}
狀態       : {row[9]}
優先順序   : {row[10]}
"""
    )


def update_ticket(ticket_id: int, status=None, summary=None):
    updated_fields = []
    now = datetime.utcnow().isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        if status:
            conn.execute(
                f"UPDATE {TABLE} SET status=?, updated_at=? WHERE id=?", (status, now, ticket_id)
            )
            updated_fields.append("狀態")
        if summary:
            conn.execute(
                f"UPDATE {TABLE} SET summary=?, updated_at=? WHERE id=?", (summary, now, ticket_id)
            )
            updated_fields.append("摘要")
        conn.commit()

    if updated_fields:
        logger.info("工單 #%d 已更新欄位：%s", ticket_id, ", ".join(updated_fields))
    else:
        logger.warning("未指定更新欄位")


def parse_args():
    parser = argparse.ArgumentParser(description="技術支援工單管理 CLI 工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="建立新工單")
    p_create.add_argument("--subject", required=True)
    p_create.add_argument("--content", required=True)
    p_create.add_argument("--summary", default="")
    p_create.add_argument("--sender")
    p_create.add_argument("--category")
    p_create.add_argument("--confidence", type=float)

    sub.add_parser("list", help="列出所有工單")

    p_show = sub.add_parser("show", help="查詢單一工單")
    p_show.add_argument("--id", required=True, type=int)

    p_update = sub.add_parser("update", help="更新工單狀態 / 摘要")
    p_update.add_argument("--id", required=True, type=int)
    p_update.add_argument("--status", choices=["pending", "done"])
    p_update.add_argument("--summary")

    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "create":
        create_ticket(
            args.subject, args.content, args.summary, args.sender, args.category, args.confidence
        )
    elif args.command == "list":
        list_tickets()
    elif args.command == "show":
        show_ticket(args.id)
    elif args.command == "update":
        update_ticket(args.id, args.status, args.summary)


if __name__ == "__main__":
    main()
