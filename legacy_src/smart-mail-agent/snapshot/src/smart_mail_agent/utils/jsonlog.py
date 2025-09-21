from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _log_dir() -> Path:
    d = Path(os.getenv("SMA_LOG_DIR", Path.cwd() / "data" / "logs"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_event(meta: Dict[str, Any], email: Dict[str, Any], result: Dict[str, Any]) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d")
    path = _log_dir() / f"events_{ts}.ndjson"
    rec = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "meta": meta,
        "email": email,
        "result": result,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # 回填 logged_path 供測試檢查
    result["logged_path"] = str(path)
    return str(path)
