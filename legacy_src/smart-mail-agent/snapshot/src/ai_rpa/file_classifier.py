#!/usr/bin/env python3
# 檔案位置: src/ai_rpa/file_classifier.py
# 模組用途: 本地檔案分類
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ai_rpa.utils.logger import get_logger

log = get_logger("FILECLS")

RULES = {
    "image": {".png", ".jpg", ".jpeg"},
    "pdf": {".pdf"},
    "text": {".txt", ".md"},
}


def classify_dir(dir_path: str) -> Dict[str, List[str]]:
    """
    走訪目錄，依副檔名分類。
    回傳:
        {"image":[...], "pdf":[...], "text":[...], "other":[...]}
    """
    p = Path(dir_path)
    out = {"image": [], "pdf": [], "text": [], "other": []}
    if not p.exists():
        log.warning("目錄不存在: %s", dir_path)
        return out
    for fp in p.rglob("*"):
        if not fp.is_file():
            continue
        ext = fp.suffix.lower()
        cat = "other"
        for k, s in RULES.items():
            if ext in s:
                cat = k
                break
        out[cat].append(str(fp))
    log.info("分類完成: %s", dir_path)
    return out
