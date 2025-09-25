from __future__ import annotations
from pathlib import Path
__all__ = ["classify"]
def classify(path: str) -> str:
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".pdf": return "pdf"
    if suf in (".jpg",".jpeg",".png",".gif",".bmp",".webp"): return "image"
    if suf in (".zip",".7z",".rar"): return "archive"
    if suf in (".txt",".md",".rtf"): return "text"
    return "unknown"
