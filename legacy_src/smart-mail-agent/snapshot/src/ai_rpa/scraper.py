from __future__ import annotations
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

def scrape(url: str) -> List[Dict[str, str]]:
    """
    下載頁面並擷取 h1/h2 文本。
    回傳: [{"tag":"h1","text":"..."}, ...]
    - 對測試 stub 友善：若沒有 raise_for_status()，就用 status_code 做基本判斷
    """
    r = requests.get(url, timeout=10)

    # 兼容測試 stub：可能沒有 raise_for_status()
    raise_status = getattr(r, "raise_for_status", None)
    if callable(raise_status):
        raise_status()
    else:
        code = int(getattr(r, "status_code", 200))
        if not (200 <= code < 300):
            raise RuntimeError(f"HTTP {code} from {url}")

    html = getattr(r, "text", "") or ""
    soup = BeautifulSoup(html, "html.parser")

    items: List[Dict[str, str]] = []
    for tag in ("h1", "h2"):
        for el in soup.find_all(tag):
            txt = (el.get_text() or "").strip()
            if txt:
                items.append({"tag": tag, "text": txt})
    return items
