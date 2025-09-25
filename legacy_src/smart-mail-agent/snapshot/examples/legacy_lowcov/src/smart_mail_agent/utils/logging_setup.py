from __future__ import annotations

import json
import logging
import os
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
            "time": int(time.time() * 1000),
        }
        # 附加 extra
        for k, v in getattr(record, "__dict__", {}).items():
            if k not in base and k not in (
                "args",
                "exc_info",
                "exc_text",
                "stack_info",
                "msg",
                "message",
            ):
                try:
                    json.dumps({k: v})
                    base[k] = v
                except Exception:
                    pass
        if record.exc_info:
            base["exc_type"] = str(record.exc_info[0].__name__)
        return json.dumps(base, ensure_ascii=False)


def setup_logging(level: str | int = None) -> logging.Logger:
    lvl = level or os.environ.get("LOG_LEVEL", "INFO")
    logger = logging.getLogger("sma")
    if not logger.handlers:
        h = logging.StreamHandler(stream=sys.stdout)
        h.setFormatter(JsonFormatter())
        logger.addHandler(h)
    logger.setLevel(lvl)
    return logger
