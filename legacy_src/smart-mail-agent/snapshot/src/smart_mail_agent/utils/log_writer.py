from __future__ import annotations

from typing import Any

# 盡量轉接到觀測模組；若該模組不存在，提供安全降級實作
try:
    # 正式實作（若存在）
    from smart_mail_agent.observability.log_writer import (
        write_log as _write_log,  # type: ignore[attr-defined]
    )
except Exception:  # pragma: no cover

    def _write_log(event: str, **fields: Any) -> None:  # 最小可用 stub
        import json
        import logging

        logging.getLogger("SMA").info(
            "[event=%s] %s", event, json.dumps(fields, ensure_ascii=False)
        )


try:
    from smart_mail_agent.observability.log_writer import (
        log_to_db as _log_to_db,  # type: ignore[attr-defined]
    )
except Exception:  # pragma: no cover

    def _log_to_db(*_a: Any, **_k: Any) -> None:
        # 安全降級：什麼都不做（保持 API 存在以通過舊測試 import）
        return None


write_log = _write_log
log_to_db = _log_to_db  # type: ignore[name-defined]
__all__ = ["write_log", "log_to_db"]


# ---------------------------------------------------------------------
# AP-13: Backward-compat shim for historical imports
# 提供一個極薄的 JsonLogWriter，僅為了讓
#   from utils.log_writer import JsonLogWriter
# 能成功匯入；其 .write(...) 會優先委派 jsonlog.log_event(...)，
# 若不相容，則回退到本模組的 write_log(...)。
# 這不更改任何現有函式，只是補上相容層。
class JsonLogWriter:
    """Backward-compat shim. Prefer calling functions directly if possible.

    Methods
    -------
    write(*args, **kwargs)
        Try smart_mail_agent.utils.jsonlog.log_event(*args, **kwargs),
        else fallback to write_log(*args, **kwargs) in this module.
    log = write
    """

    def __init__(self, *_, **__):
        # 保持與未知舊簽名相容：接收任意參數但不使用
        pass

    def write(self, *args, **kwargs):  # pylint: disable=unused-argument
        # 優先使用 jsonlog.log_event
        try:
            from smart_mail_agent.utils.jsonlog import log_event  # lazy import

            try:
                return log_event(*args, **kwargs)
            except TypeError:
                # 簽名不合時再回退
                pass
        except Exception:
            # 模組不存在或其它錯誤則回退
            pass

        # 回退到本模組函式（若存在）
        try:
            return write_log(*args, **kwargs)  # type: ignore[name-defined]
        except Exception as e:  # 最終防護，避免靜默失敗
            raise RuntimeError(
                "JsonLogWriter.write() fallback failed. "
                "Consider using smart_mail_agent.utils.jsonlog.log_event "
                "or write_log(...) directly."
            ) from e

    # 常見別名
    log = write

    # 安全的 context manager (不做任何資源管理，只為相容)
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


# 確保匯出符號
try:
    __all__  # type: ignore[name-defined]
    if "JsonLogWriter" not in __all__:
        __all__.append("JsonLogWriter")  # type: ignore[index]
except Exception:
    try:
        __all__ = list(sorted(set(globals().get("__all__", [])) | {"JsonLogWriter"}))
    except Exception:
        pass
# ---------------------------------------------------------------------
