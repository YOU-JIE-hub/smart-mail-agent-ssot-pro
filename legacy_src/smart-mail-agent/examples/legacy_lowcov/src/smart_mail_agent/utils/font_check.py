from __future__ import annotations

import os

#!/usr/bin/env python3
from pathlib import Path


def get_font_path(env_key: str = "FONT_PATH") -> str | None:
    p = os.getenv(env_key, "").strip()
    if not p:
        return None
    path = Path(p)
    return str(path) if path.is_file() else None


def ensure_font_available(logger=None) -> str | None:
    fp = get_font_path()
    if fp is None:
        msg = "未找到中文字型 FONT_PATH，PDF 中文輸出可能失敗；請放置 assets/fonts/NotoSansTC-Regular.ttf 並更新 .env"
        (logger.warning if logger else print)(msg)
        return None
    return fp
