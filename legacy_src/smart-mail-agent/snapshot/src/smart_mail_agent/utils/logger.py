from __future__ import annotations

import logging
import os

_ENV = "SMA_LOG_LEVEL"
_DEFAULT = "INFO"


def _level_from_env() -> int:
    lvl = (os.getenv(_ENV, _DEFAULT) or _DEFAULT).upper()
    return getattr(logging, lvl, logging.INFO)


def get_logger(name: str | None = None) -> logging.Logger:
    base = "ai_rpa"
    if name:
        nm = name.strip(".")
        full = nm if nm.startswith(f"{base}.") else f"{base}.{nm}"
    else:
        full = base
    lg = logging.getLogger(full)
    lg.setLevel(_level_from_env())
    # 關鍵：不要自掛 handler，用 propagate=True 讓 pytest 的 caplog root handler 捕捉
    lg.propagate = True
    return lg


# 模組層預設 logger（可用但單測不依賴）
logger = get_logger()
