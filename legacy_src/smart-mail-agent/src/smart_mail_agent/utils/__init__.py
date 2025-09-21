from __future__ import annotations

from importlib import import_module as _im

# 讓 "from smart_mail_agent.utils import logger" 取得的是子模組物件，而不是同名變數
logger = _im(__name__ + ".logger")  # type: ignore[assignment]

__all__ = ["logger"]
