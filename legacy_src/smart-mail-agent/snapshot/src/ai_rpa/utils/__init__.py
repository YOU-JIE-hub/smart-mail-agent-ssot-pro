from __future__ import annotations

from importlib import import_module as _im

logger = _im(__name__ + ".logger")  # type: ignore[assignment]

__all__ = ["logger"]
