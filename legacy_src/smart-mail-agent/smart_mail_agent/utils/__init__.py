#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import logging, os, hashlib, json, datetime as _dt
from pathlib import Path
from typing import Iterable, Dict, Any

_LOG_LEVEL = os.getenv("SMA_LOG_LEVEL", "INFO").upper()
_FORMAT = os.getenv("SMA_LOG_FMT", "%(asctime)s %(levelname)s %(name)s: %(message)s")

def _setup_root_once():
    root = logging.getLogger("smart_mail_agent")
    if not root.handlers:
        h = logging.StreamHandler()
        fmt = logging.Formatter(_FORMAT)
        h.setFormatter(fmt)
        root.addHandler(h)
        try:
            root.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))
        except Exception:
            root.setLevel(logging.INFO)
    return root

def logger(name: str = "smart_mail_agent") -> logging.Logger:
    """Return a namespaced logger under 'smart_mail_agent' (idempotent)."""
    _setup_root_once()
    return logging.getLogger(name if name.startswith("smart_mail_agent") else f"smart_mail_agent.{name}")

# ---- 非侵入小工具（可能被測試用到；不會破壞你現有流程） -----------------------
def sha1_of_text(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8", "ignore")).hexdigest()

def ensure_dir(p: Path | str) -> Path:
    p = Path(p); p.mkdir(parents=True, exist_ok=True); return p

def utcnow_iso() -> str:
    return _dt.datetime.utcnow().replace(tzinfo=_dt.timezone.utc).isoformat()

def read_jsonl(path: Path | str) -> Iterable[Dict[str, Any]]:
    p = Path(path)
    if not p.exists(): return []
    for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not ln.strip(): continue
        yield json.loads(ln)
