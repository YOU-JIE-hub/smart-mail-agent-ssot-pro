#!/usr/bin/env python3
# 檔案位置: src/ai_rpa/utils/config_loader.py
# 模組用途: 載入 YAML 配置與 .env，集中管理參數
from __future__ import annotations

import os
from typing import Any, Dict

import yaml

DEFAULT_CONFIG: Dict[str, Any] = {
    "input_path": "data/input",
    "output_path": "data/output/report.json",
    "tasks": ["ocr", "scrape", "classify_files", "nlp", "actions"],
    "nlp": {"model": "offline-keyword"},
}


def load_config(path: str | None) -> Dict[str, Any]:
    """
    載入設定檔（YAML），若缺失則回退預設。
    參數:
        path: 設定檔路徑
    回傳:
        dict: 設定字典
    """
    cfg = DEFAULT_CONFIG.copy()
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg.update(data)
    # 企業標準：字型與 PDF 目錄（若缺失則給出 fallback）
    cfg["fonts_path"] = os.getenv("FONTS_PATH", "assets/fonts/NotoSansTC-Regular.ttf")
    cfg["pdf_output_dir"] = os.getenv("PDF_OUTPUT_DIR", "share/output")
    return cfg
