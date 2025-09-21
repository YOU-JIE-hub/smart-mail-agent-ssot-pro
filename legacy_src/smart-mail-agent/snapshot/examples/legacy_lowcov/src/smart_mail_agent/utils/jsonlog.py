from __future__ import annotations

import datetime as dt
import json
import os

#!/usr/bin/env python3
from pathlib import Path
from typing import Any


def _log_dir() -> Path:
    d = Path(os.getenv("SMA_LOG_DIR", "logs"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _jsonable(x: Any):
    try:
        json.dumps(x)
        return x
    except Exception:
        try:
            return str(x)
        except Exception:
            return "<unserializable>"


def _to_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    for attr in ("model_dump", "dict"):
        fn = getattr(obj, attr, None)
        if callable(fn):
            try:
                return fn(by_alias=True) if attr == "model_dump" else fn()
            except Exception:
                pass
    return {"repr": repr(obj)}


def log_event(result: Any, request: dict[str, Any] | None = None) -> str:
    """Never-throw JSONL logger. Also sets result['logged_path'] when possible."""
    try:
        p = _log_dir() / f"sma-{dt.datetime.now():%Y%m%d}.jsonl"
        rd = _to_dict(result)
        row = {
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "level": "INFO",
            "action_name": rd.get("action_name"),
            "ok": bool(rd.get("ok", True)),
            "code": rd.get("code", "OK"),
            "request_id": rd.get("request_id"),
            "intent": rd.get("intent"),
            "confidence": rd.get("confidence"),
            "duration_ms": rd.get("duration_ms") or rd.get("spent_ms"),
            "dry_run": rd.get("dry_run"),
            "warnings": rd.get("warnings") or [],
        }
        if isinstance(request, dict):
            row["req_subject"] = request.get("subject")
            row["req_from"] = request.get("from")
        with p.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps({k: _jsonable(v) for k, v in row.items()}, ensure_ascii=False) + "\n"
            )
        try:
            if isinstance(result, dict):
                result["logged_path"] = str(p)
        except Exception:
            pass
        return str(p)
    except Exception as e:
        try:
            dbg = _log_dir() / "log_event_error.txt"
            dbg.write_text(
                (dbg.read_text(encoding="utf-8") if dbg.exists() else "")
                + f"[{dt.datetime.now().isoformat(timespec='seconds')}] {type(e).__name__}: {e}\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        try:
            if isinstance(result, dict):
                result.setdefault("warnings", []).append("log_write_failed")
        except Exception:
            pass
        return ""
