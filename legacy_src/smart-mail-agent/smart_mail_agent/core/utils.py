from __future__ import annotations
import os, json, datetime as _dt
from pathlib import Path
__all__ = ["jsonlog"]
def jsonlog(stage: str, **fields):
    """將事件寫入 reports_auto/logs/pipeline.ndjson（若目錄不存在自動建立）"""
    path = Path("reports_auto/logs/pipeline.ndjson")
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": _dt.datetime.utcnow().isoformat(timespec="seconds")+"Z","stage": stage}
    rec.update(fields or {})
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False)+"\n")
    return rec
