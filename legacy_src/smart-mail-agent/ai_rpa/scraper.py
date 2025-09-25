from __future__ import annotations
from typing import Any, Dict
__all__ = ["offline_get"]
def offline_get(url: str, **kw) -> Dict[str,Any]:
    return {"url": url, "status": "offline", "content": ""}
