# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict

QUOTES_DIR = Path(os.environ.get("QUOTES_DIR", "quotes"))
QUOTES_DIR.mkdir(parents=True, exist_ok=True)


def _safe_stem(name: str) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", name or "")
    s = re.sub(r"_+", "_", s).strip("._")
    return s or "_"


def _write_minimal_pdf(lines: list[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        f.write(b"%PDF-1.4\n% minimal\n")
        for ln in lines:
            f.write(b"% " + ln.encode("utf-8", "ignore") + b"\n")
        f.write(b"%%EOF\n")


def generate_pdf_quote(package: str, client_name: str) -> str:
    stem = _safe_stem(client_name)
    out = QUOTES_DIR / f"{stem}.pdf"
    _write_minimal_pdf([f"Client: {client_name}", f"Package: {package}"], out)
    return str(out)


def choose_package(subject: str = "", body: str = "") -> Dict[str, Any]:
    """
    舊介面雙參數版本：回傳 三層級名稱【基礎 / 專業 / 企業】
    """
    text = f"{subject} {body}"
    text_low = text.lower()

    has_integ = (
        ("整合" in text)
        or ("串接" in text)
        or ("erp" in text_low)
        or ("line" in text_low)
        or ("api" in text_low)
    )
    has_auto = (
        ("自動" in text)
        or ("自動化" in text)
        or ("自動分類" in text)
        or ("排程" in text)
        or ("workflow" in text_low)
        or ("rpa" in text_low)
    )
    has_price = (
        ("報價" in text)
        or ("價格" in text)
        or ("價位" in text)
        or ("詢價" in text)
        or ("quotation" in text_low)
        or ("quote" in text_low)
    )

    if has_integ:
        pkg = "企業"
    elif has_auto:
        pkg = "專業"
    elif has_price:
        pkg = "基礎"
    else:
        pkg = "企業"

    return {"package": pkg, "needs_manual": False}
