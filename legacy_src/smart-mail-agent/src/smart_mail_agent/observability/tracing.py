from __future__ import annotations

# -*- coding: utf-8 -*-
import time
import uuid


def uuid_str() -> str:
    return str(uuid.uuid4())


def now_ms() -> int:
    return int(time.time() * 1000)


def elapsed_ms(start_ms: int) -> int:
    try:
        return max(0, now_ms() - int(start_ms))
    except Exception:
        return 0
