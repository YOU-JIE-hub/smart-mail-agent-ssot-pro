from __future__ import annotations

import os

# -*- coding: utf-8 -*-


def get_bool(keys, default=False):
    if isinstance(keys, str):
        keys = [keys]
    for k in keys:
        v = os.environ.get(k)
        if v is None:
            continue
        s = str(v).strip().lower()
        return s in ("1", "true", "yes", "y", "on")
    return default
