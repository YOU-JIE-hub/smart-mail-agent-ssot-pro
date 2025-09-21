from __future__ import annotations
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Iterable

def jsonable(obj: Any) -> Any:
    """遞迴轉為可 JSON 序列化的型別，避免 Path/Exception/set 之類噴錯。"""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Exception):
        return f"{obj.__class__.__name__}: {obj}"
    if is_dataclass(obj):
        return jsonable(asdict(obj))
    if isinstance(obj, Mapping):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [jsonable(x) for x in obj]
    # fallback
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"
