from __future__ import annotations
import os, sqlite3
from pathlib import Path
__all__ = ["ensure_db","ensure_schema"]
def ensure_db(path: str = "db/sma.sqlite") -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(path).close()
    return path
def ensure_schema(path: str = "db/sma.sqlite") -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE IF NOT EXISTS actions(id TEXT, action TEXT, priority TEXT, queue TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS intent_preds(final TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS kie_spans(label TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS err_log(ts TEXT, mail_id TEXT, stage TEXT, message TEXT, traceback TEXT)")
        con.commit()
    finally:
        con.close()
