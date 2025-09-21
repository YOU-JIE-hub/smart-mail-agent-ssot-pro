from __future__ import annotations
from typing import Dict, List, Iterable, Any
from pathlib import Path
import re, mimetypes

__all__ = [
    "classify_text",
    "classify_bytes",
    "classify_file",
    "classify_path",   # <- conftest 會呼叫這個
    "classify_dir",
]

# ---- heuristics ----
_EXT_MAP = {
    # office / docs
    ".pdf":      ["pdf", "document"],
    ".doc":      ["document"],
    ".docx":     ["document"],
    ".rtf":      ["document"],
    ".md":       ["document", "text"],
    ".txt":      ["text", "document"],
    ".csv":      ["spreadsheet"],
    ".xls":      ["spreadsheet"],
    ".xlsx":     ["spreadsheet"],
    ".ppt":      ["presentation"],
    ".pptx":     ["presentation"],
    # images
    ".png":      ["image"],
    ".jpg":      ["image"],
    ".jpeg":     ["image"],
    ".gif":      ["image"],
    ".bmp":      ["image"],
    # others
    ".json":     ["data"],
    ".yaml":     ["data"],
    ".yml":      ["data"],
    ".log":      ["log", "text"],
}

_TXT_HINTS = [
    (r"發票|invoice",         "invoice"),
    (r"退款|退費|refund",      "policy_refund"),
    (r"使用\s*限制|terms|EULA","policy_terms"),
    (r"客服|支援|ticket",      "support"),
    (r"合約|contract",         "contract"),
    (r"報價|價格|quote|price", "quote"),
    (r"會議|行程|meeting",     "calendar"),
    (r"身分證|passport|ID",    "id_document"),
]

def _norm(s: str) -> str:
    return (s or "").strip()

def classify_text(text: str, filename: str | None = None) -> Dict[str, Any]:
    """
    文本/檔名 雙訊號的簡易規則分類；回傳 {labels:[], hints:[], filename:str}
    """
    labels: List[str] = []
    hints: List[str] = []
    t = _norm(text)
    fn = _norm(filename or "")
    ext = Path(fn).suffix.lower()

    # by extension
    labels.extend(_EXT_MAP.get(ext, []))

    # generic text/image/log if mime says so
    if not labels and ext:
        guess, _ = mimetypes.guess_type(fn)
        if guess:
            if guess.startswith("text/"):
                labels.append("text")
            elif guess.startswith("image/"):
                labels.append("image")

    # keyword hints from text
    if t:
        for pat, lab in _TXT_HINTS:
            if re.search(pat, t, re.I):
                hints.append(lab)
                if lab not in labels:
                    labels.append(lab)

    # filename keywords
    if fn:
        for pat, lab in _TXT_HINTS:
            if re.search(pat, fn, re.I):
                if lab not in labels:
                    labels.append(lab)
                if lab not in hints:
                    hints.append(lab)

    # minimal fallback
    if not labels:
        labels.append("unknown")

    return {"labels": labels, "hints": hints, "filename": fn}

def _looks_textual(sample: bytes) -> bool:
    if not sample:
        return True
    # PDF / PNG magic 防誤判
    if sample.startswith(b"%PDF-"):
        return False
    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    # 有太多 NUL/控制碼視為二進位
    ctrl = sum(1 for b in sample if b < 9 or (13 < b < 32))
    nul  = sample.count(0)
    return nul == 0 and ctrl <= max(1, len(sample)//20)

def classify_bytes(data: bytes, filename: str | None = None) -> Dict[str, Any]:
    """
    只讀前 4KB 估計：PDF/PNG magic、可讀率、再丟到 classify_text 做關鍵字判斷。
    """
    sample = data[:4096] if isinstance(data, (bytes, bytearray)) else b""
    if sample.startswith(b"%PDF-"):
        base = {"labels": ["pdf", "document"], "hints": ["pdf_magic"], "filename": _norm(filename or "")}
        return base
    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        base = {"labels": ["image"], "hints": ["png_magic"], "filename": _norm(filename or "")}
        return base

    if _looks_textual(sample):
        try:
            text = sample.decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        return classify_text(text, filename=filename)

    # binary fallback
    out = classify_text("", filename=filename)
    if "image" not in out["labels"]:
        out["labels"].append("binary")
    return out

def classify_file(path: str | Path) -> Dict[str, Any]:
    """
    檔案分類（讀入 bytes + 檔名規則）
    """
    p = Path(path)
    try:
        data = p.read_bytes()
    except Exception as e:
        return {"labels": ["unreadable"], "hints": [f"error:{type(e).__name__}"], "filename": str(p)}
    return classify_bytes(data, filename=p.name)

# 別名：conftest 會呼叫 classify_path
def classify_path(path: str | Path) -> Dict[str, Any]:
    return classify_file(path)

def classify_dir(dirpath: str | Path) -> List[Dict[str, Any]]:
    """
    便利目錄中常見檔案；回傳每檔案一筆 result
    """
    d = Path(dirpath)
    out: List[Dict[str, Any]] = []
    if not d.exists() or not d.is_dir():
        return out
    for p in d.iterdir():
        if p.is_file():
            out.append(classify_file(p))
    return out
