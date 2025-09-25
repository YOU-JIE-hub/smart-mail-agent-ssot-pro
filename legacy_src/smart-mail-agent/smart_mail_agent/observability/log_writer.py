from __future__ import annotations
import os, json, sqlite3, datetime as _dt
from pathlib import Path
from typing import Any, Mapping

__all__ = ["log_to_db", "log_to_ndjson"]

_DEF_DB = "db/sma.sqlite"
_DEF_TABLE = "logs"
_DEF_NDJSON = "reports_auto/logs/pipeline.ndjson"

def _mkdir_of(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

def _now_iso() -> str:
    return _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

def log_to_db(
    record: Mapping[str, Any],
    *,
    db_path: str = _DEF_DB,
    table: str = _DEF_TABLE,
) -> str:
    """
    將 record 落到 SQLite。欄位盡量寬鬆，未知欄位放到 extra(JSON)。
    成功回傳 db_path。
    """
    ts      = str(record.get("ts") or _now_iso())
    level   = str(record.get("level") or record.get("severity") or "INFO")
    stage   = str(record.get("stage") or "")
    message = str(record.get("message") or record.get("msg") or "")
    mail_id = str(record.get("mail_id") or record.get("id") or "")

    # 其餘欄位打包進 extra
    extra_keys = {"ts","level","severity","stage","message","msg","mail_id","id"}
    extra = {k: v for k, v in record.items() if k not in extra_keys}

    _mkdir_of(db_path)
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "ts TEXT, level TEXT, stage TEXT, message TEXT, mail_id TEXT, extra TEXT)"
        )
        con.execute(
            f"INSERT INTO {table} (ts,level,stage,message,mail_id,extra) VALUES (?,?,?,?,?,?)",
            (ts, level, stage, message, mail_id, json.dumps(extra, ensure_ascii=False)),
        )
        con.commit()
    finally:
        con.close()
    return db_path

def log_to_ndjson(
    record: Mapping[str, Any],
    *,
    path: str = _DEF_NDJSON,
) -> str:
    """
    追加寫入 NDJSON 審計流水。成功回傳檔案路徑。
    """
    if "ts" not in record:
        record = {**record, "ts": _now_iso()}
    _mkdir_of(path)
    with open(path, "a", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False)
        f.write("\n")
    return path
