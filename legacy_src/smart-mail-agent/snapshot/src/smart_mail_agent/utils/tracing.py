from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def trace_decision(root: Path, name: str, payload: dict[str, Any]) -> Path:
    out_dir = root / "data" / "output" / "traces"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    p = out_dir / f"{ts}_{name}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
