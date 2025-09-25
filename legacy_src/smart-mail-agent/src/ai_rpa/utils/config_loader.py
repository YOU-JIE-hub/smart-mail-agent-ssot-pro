from __future__ import annotations
from typing import Any, Dict

def load(path: str | None) -> Dict[str,Any]:
    return {} if not path else {"path": path}
