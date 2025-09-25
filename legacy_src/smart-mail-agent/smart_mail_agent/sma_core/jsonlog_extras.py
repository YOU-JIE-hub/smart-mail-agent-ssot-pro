from __future__ import annotations
import json, datetime as _dt
from typing import Any, Mapping
from ..observability.log_writer import log_to_ndjson

__all__ = ["jsonable","ensure_ts","write_ndjson_line"]

def jsonable(x: Any) -> Any:
    try:
        json.dumps(x)
        return x
    except Exception:
        return str(x)

def ensure_ts(rec: Mapping[str, Any]) -> dict:
    d = dict(rec)
    if "ts" not in d:
        d["ts"] = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return d

def write_ndjson_line(rec: Mapping[str, Any], path: str = "reports_auto/logs/pipeline.ndjson") -> str:
    return log_to_ndjson(ensure_ts(rec), path=path)
