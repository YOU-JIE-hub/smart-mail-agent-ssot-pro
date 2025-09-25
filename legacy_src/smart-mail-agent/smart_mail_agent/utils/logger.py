from __future__ import annotations
import logging, os, sys
from logging.handlers import RotatingFileHandler

__all__ = ["get_logger", "logger"]

def _level_from_env(default: str = "INFO") -> int:
    lvl = str(os.environ.get("SMA_LOG_LEVEL", default)).upper()
    return getattr(logging, lvl, logging.INFO)

def get_logger(name: str = "sma", *, level: str | int | None = None, to_file: str | None = None) -> logging.Logger:
    """
    回傳可重入的 logger：
      - 預設輸出到 stdout
      - 若設定 to_file 或 SMA_LOG_FILE 則同時寫檔（旋轉）
      - 以 SMA_LOG_LEVEL 控制等級（預設 INFO）
    """
    log = logging.getLogger(name)
    if getattr(log, "_sma_configured", False):
        return log
    lvl = _level_from_env() if level is None else (getattr(logging, str(level).upper(), logging.INFO) if isinstance(level, str) else int(level))
    log.setLevel(lvl)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setLevel(lvl); sh.setFormatter(fmt)
    log.addHandler(sh)

    fp = to_file or os.environ.get("SMA_LOG_FILE")
    if fp:
        os.makedirs(os.path.dirname(fp) or ".", exist_ok=True)
        fh = RotatingFileHandler(fp, maxBytes=1_048_576, backupCount=3)
        fh.setLevel(lvl); fh.setFormatter(fmt)
        log.addHandler(fh)

    log._sma_configured = True
    return log

def logger(name: str = "sma", **kw) -> logging.Logger:
    return get_logger(name, **kw)
