from __future__ import annotations

#!/usr/bin/env python3
# 檔案位置：src/log_writer.py
# 模組用途：統一寫入 emails_log.db 的工具（企業級欄位與穩定介面）
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# 統一日誌格式
logger = logging.getLogger("log_writer")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [log_writer] %(message)s",
    )

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "emails_log.db"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """建立 emails_log 資料表（若不存在）。"""
    conn.execute(
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


def log_to_db(
    subject: str,
    content: str = "",
    summary: str = "",
    predicted_label: str | None = None,
    confidence: float | None = None,
    action: str = "",
    error: str = "",
    db_path: Path | None = None,
) -> int:
    """寫入一筆處理紀錄到 emails_log.db。

    參數：
        subject: 題目/主旨
        content: 內文（可省略）
        summary: 摘要（可省略）
        predicted_label: 預測分類（可省略）
        confidence: 信心值（可省略）
        action: 採取動作（可省略）
        error: 錯誤訊息（可省略）
        db_path: 自訂 DB 路徑（測試用）

    回傳：
        新增記錄的 rowid（int）
    """
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        _ensure_schema(conn)
        cur = conn.execute(
            """
            INSERT INTO emails_log (
                subject, content, summary, predicted_label,
                confidence, action, error, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subject,
                content,
                summary,
                predicted_label,
                float(confidence) if confidence is not None else None,
                action,
                error,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        rowid = int(cur.lastrowid or 0)
        logger.info(
            "已記錄：%s / %s / 信心 %s",
            predicted_label or "-",
            action or "-",
            f"{confidence:.4f}" if confidence is not None else "-",
        )
        return rowid
    finally:
        conn.close()


if __name__ == "__main__":
    # 提供簡易 CLI：python -m src.log_writer "主旨" --label "分類"
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("subject", help="主旨")
    parser.add_argument("--content", default="", help="內文")
    parser.add_argument("--summary", default="", help="摘要")
    parser.add_argument("--label", dest="predicted_label", default=None, help="分類")
    parser.add_argument("--confidence", type=float, default=None, help="信心值")
    parser.add_argument("--action", default="", help="動作")
    parser.add_argument("--error", default="", help="錯誤訊息")
    args = parser.parse_args()

    log_to_db(
        subject=args.subject,
        content=args.content,
        summary=args.summary,
        predicted_label=args.predicted_label,
        confidence=args.confidence,
        action=args.action,
        error=args.error,
    )
    print("[OK] 已寫入 emails_log")
