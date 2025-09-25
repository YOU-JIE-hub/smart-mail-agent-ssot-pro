from __future__ import annotations

import sqlite3
from pathlib import Path

from smart_mail_agent.utils.logger import get_logger

logger = get_logger("smart_mail_agent")

DB_PATH: str | Path = "stats.db"


def _dbp() -> Path:
    p = Path(DB_PATH) if not isinstance(DB_PATH, Path) else DB_PATH
    return Path(p)


def init_stats_db() -> None:
    path = _dbp()
    try:
        if path.parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as c:
            c.execute(
                """CREATE TABLE IF NOT EXISTS stats(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT,
                elapsed REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
            )
    except Exception as e:
        logger.error("[STATS] 初始化資料庫失敗：%s", e)
        raise


def increment_counter(label: str, elapsed: float) -> None:
    try:
        with sqlite3.connect(_dbp()) as c:
            c.execute("INSERT INTO stats(label, elapsed) VALUES(?,?)", (label, float(elapsed)))
    except Exception as e:
        logger.warning("[STATS] 寫入失敗：%s", e)
