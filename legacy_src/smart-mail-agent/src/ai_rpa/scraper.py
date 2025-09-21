from __future__ import annotations
import os
from typing import Any, Dict, List

def scrape(url: str) -> List[Dict[str, Any]]:
    if not url:
        return []
    if os.environ.get("OFFLINE") == "1":
        return []
    # 可擴充真實爬取；測試中通常 monkeypatch 或 OFFLINE
    return []
