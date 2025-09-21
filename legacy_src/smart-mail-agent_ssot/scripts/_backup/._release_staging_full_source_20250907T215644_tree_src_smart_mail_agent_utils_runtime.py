from __future__ import annotations

import json
import os
import pathlib
import time
import uuid


def run_id() -> str:
    rid = os.getenv("SMA_RUN_ID")
    if rid:
        return rid
    rid = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    os.environ["SMA_RUN_ID"] = rid
    return rid


def write_jsonl(path: str | os.PathLike[str], obj: dict | None = None) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    item = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_id": os.getenv("SMA_RUN_ID", "-"), **(obj or {})}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
