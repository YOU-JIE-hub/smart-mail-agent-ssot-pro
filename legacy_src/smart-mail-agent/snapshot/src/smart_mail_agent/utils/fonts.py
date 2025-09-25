#!/usr/bin/env python3
from __future__ import annotations

import os

# 檔案位置: src/smart_mail_agent/utils/fonts.py
from pathlib import Path

PREFERRED = ("NotoSansTC-Regular.ttf",)


def find_font(root: str | Path = ".") -> str | None:
    env_font = os.getenv("FONT_PATH")
    if env_font and Path(env_font).is_file():
        return env_font
    root = Path(root).resolve()
    for name in PREFERRED:
        p = root / "assets" / "fonts" / name
        if p.is_file():
            return str(p)
    return None
