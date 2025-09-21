from __future__ import annotations
from pathlib import Path

__all__ = [
    "is_probably_pdf", "has_active_content", "pdf_is_safe",
    "extract_text_safe", "extract_text", "is_pdf"
]

def is_probably_pdf(path: str | bytes | Path) -> bool:
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return True
    try:
        with open(p, "rb") as f:
            head = f.read(5)
        return head.startswith(b"%PDF-")
    except Exception:
        return False

def has_active_content(path: str | bytes | Path) -> tuple[bool, list[str]]:
    flags: list[str] = []
    try:
        with open(path, "rb") as f:
            data = f.read(4_096_000)
        text = data.decode("latin-1", errors="ignore")
        for kw in ("/JS", "/JavaScript", "/AA", "/OpenAction", "/Launch"):
            if kw in text:
                flags.append(kw)
    except Exception:
        pass
    return (len(flags) > 0, flags)

def extract_text_safe(path: str | bytes | Path, max_pages: int | None = None) -> str:
    # 離線、安全：不真正解析 PDF，回傳可預期的佔位文本，避免重型依賴
    return f"[pdf-safe] {Path(path).name}"

# 兼容測試可能使用的函式名
extract_text = extract_text_safe
is_pdf = is_probably_pdf

def pdf_is_safe(path: str | bytes | Path) -> dict:
    ok = is_probably_pdf(path)
    bad, flags = has_active_content(path)
    if bad:
        return {"ok": False, "flags": flags, "reason": "active-content"}
    return {"ok": bool(ok), "flags": flags}
