from __future__ import annotations
import json, math, re, sys, enum, datetime as _dt
from pathlib import Path
from decimal import Decimal
from typing import Any, Mapping, Iterable

__all__ = ["normalize_result", "jsonable", "to_plain"]

# 可選：輕量處理 numpy 類型（若環境沒有 numpy，邏輯不報錯）
try:
    import numpy as _np  # type: ignore
    _HAS_NP = True
except Exception:
    _HAS_NP = False

def _is_np_scalar(x: Any) -> bool:
    return _HAS_NP and getattr(type(x), "__module__", "").startswith("numpy") and hasattr(x, "item")

def _np_to_py(x: Any) -> Any:
    if not _HAS_NP:
        return x
    try:
        if hasattr(x, "tolist"):
            return x.tolist()
        if hasattr(x, "item"):
            return x.item()
    except Exception:
        pass
    return x

def jsonable(x: Any) -> Any:
    """若無法 json.dumps，退回字串表示（保證不炸）。"""
    try:
        json.dumps(x)
        return x
    except Exception:
        return str(x)

def _try_sort_list(xs: list[Any]) -> list[Any]:
    """為了可比較與測試穩定性，嘗試排序同質元素；異質時維持原順序。"""
    try:
        return sorted(xs)
    except Exception:
        return xs

def to_plain(x: Any) -> Any:
    """把常見非 JSON 類型轉成純 Python 結構。"""
    # None/布林/數字/字串：直接回傳（NaN/Inf 正規化）
    if x is None or isinstance(x, (bool, int, float, str)):
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return None
        return x

    # Decimal -> float（若失敗回字串）
    if isinstance(x, Decimal):
        try:
            return float(x)
        except Exception:
            return str(x)

    # datetime/date -> ISO 8601
    if isinstance(x, (_dt.datetime, _dt.date)):
        try:
            if isinstance(x, _dt.datetime) and x.tzinfo is None:
                # 標準化為 UTC 假設，避免測試不穩
                return x.replace(tzinfo=_dt.timezone.utc).isoformat()
            return x.isoformat()
        except Exception:
            return str(x)

    # pathlib.Path
    if isinstance(x, Path):
        return str(x)

    # bytes/bytearray -> UTF-8 解碼；失敗則 hex 短標記
    if isinstance(x, (bytes, bytearray)):
        try:
            return x.decode("utf-8", errors="ignore")
        except Exception:
            return f"<bytes:{len(x)}>"

    # Enum
    if isinstance(x, enum.Enum):
        return x.value if not isinstance(x.value, enum.Enum) else str(x)

    # numpy 系列
    if _is_np_scalar(x) or getattr(x, "tolist", None):
        return to_plain(_np_to_py(x))

    # dict
    if isinstance(x, Mapping):
        out = {}
        for k, v in x.items():
            # key 標準化為字串
            ks = str(k)
            out[ks] = to_plain(v)
        return out

    # set/frozenset -> 排序後 list
    if isinstance(x, (set, frozenset)):
        return _try_sort_list([to_plain(i) for i in x])

    # tuple/list -> list
    if isinstance(x, (tuple, list)):
        return [to_plain(i) for i in x]

    # 其他可迭代但不是字串
    if isinstance(x, Iterable) and not isinstance(x, (str, bytes, bytearray)):
        try:
            return [to_plain(i) for i in x]
        except Exception:
            return str(x)

    # 其他物件：盡量取 __dict__，否則字串化
    d = getattr(x, "__dict__", None)
    if isinstance(d, dict) and d:
        return to_plain(d)

    return str(x)

def normalize_result(obj: Any) -> Any:
    """
    高容錯正規化：
     - 遞迴轉成純 Python 結構（dict/list/str/float/bool/None）
     - dict key -> str
     - set/tuple -> list；嘗試排序同質元素，確保測試穩定
     - NaN/Inf -> None；datetime/date -> ISO8601（無 tz 視為 UTC）
     - numpy/Decimal/Enum/Path/bytes 等全涵蓋
    """
    plain = to_plain(obj)
    # 再跑一次 jsonable，保證可序列化
    return jsonable(plain)
