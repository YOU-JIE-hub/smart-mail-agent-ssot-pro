from __future__ import annotations
import re

_ws = re.compile(r"\s+", re.U)
_tok = re.compile(r"[0-9A-Za-z\u4e00-\u9fff]+", re.U)

def norm(t: str) -> str:
    return _ws.sub(" ", (t or "").strip())

def tokenize(t: str):
    return _tok.findall((t or "").lower())
