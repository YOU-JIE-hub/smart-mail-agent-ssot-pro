from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from ai_rpa.utils.json_safe import to_jsonable

def write_json(data: Any, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(to_jsonable(data), ensure_ascii=False, indent=2), encoding="utf-8")
