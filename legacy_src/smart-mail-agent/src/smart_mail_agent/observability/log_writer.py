from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Tuple

# 欄位順序與資料表欄位一致
COLS = ("subject", "content", "summary", "predicted_label", "confidence", "action", "error")

# 預設值：若呼叫端未提供就自動補上
_DEFAULTS: Dict[str, Any] = {
    "subject": "",
    "content": "",
    "summary": "",
    "predicted_label": "",
    "confidence": None,  # REAL 欄位允許 NULL
    "action": "",
    "error": "",
}


def _normalize_args(*args, **kwargs) -> Tuple[Dict[str, Any], Path]:
    """
    支援兩種呼叫方式：
      1) 位置參數：log_to_db(subject, content, summary, predicted_label, confidence, action, error, db_path=...)
         可傳 1~7 個位置參數；缺的會自動補預設值。
      2) 具名參數：log_to_db(subject="S", db_path=tmpdb, ...)；缺的會自動補預設值。
    必填：db_path（Path 或 str）
    """
    dbp = kwargs.get("db_path")
    if not dbp:
        raise TypeError("需要 db_path= Path/str")
    if args:
        # 允許只給前面幾個位置參數，其餘自動補
        vals = list(args[:7]) + [None] * max(0, 7 - len(args))
        data = {k: (vals[i] if vals[i] is not None else _DEFAULTS[k]) for i, k in enumerate(COLS)}
    else:
        data = {k: kwargs.get(k, _DEFAULTS[k]) for k in COLS}
    return data, Path(dbp)


def _ensure_schema(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS emails_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        subject TEXT,
        content TEXT,
        summary TEXT,
        predicted_label TEXT,
        confidence REAL,
        action TEXT,
        error TEXT
    )"""
    )


def log_to_db(*args, **kwargs) -> int:
    """
    回傳新寫入列的 id（int）。
    參數見 _normalize_args；務必提供 db_path。
    """
    data, db_path = _normalize_args(*args, **kwargs)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as c:
        _ensure_schema(c)
        cur = c.execute(
            "INSERT INTO emails_log(subject,content,summary,predicted_label,confidence,action,error) VALUES(?,?,?,?,?,?,?)",
            [data[k] for k in COLS],
        )
        return int(cur.lastrowid)
