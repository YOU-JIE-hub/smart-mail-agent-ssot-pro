from __future__ import annotations
from pathlib import Path
from typing import Any
import base64, datetime, json

__all__ = [
    "ensure_jsonable", "dumps_safe", "dump_safe",
    # 兼容別名
    "to_jsonable", "json_dumps", "dumps", "dump"
]

_JSON_PRIMS = (type(None), bool, int, float, str)

def ensure_jsonable(obj: Any, _depth: int = 0) -> Any:
    """
    將各種 Python 物件安全地轉為可 JSON 序列化的型別。
    規則：
      - bytes/bytearray: 優先 UTF-8；否則 {"__bytes_b64__": "..."}
      - set/tuple: 轉 list
      - Path: 轉字串
      - datetime/date/time: isoformat()
      - Exception: {"__exc__": 類名, "msg": 訊息}
      - dict: key 統一轉字串，value 遞迴處理
      - 其他型別：repr(obj)
    """
    if isinstance(obj, _JSON_PRIMS):
        return obj

    if isinstance(obj, (bytes, bytearray)):
        try:
            return bytes(obj).decode("utf-8")
        except Exception:
            return {"__bytes_b64__": base64.b64encode(bytes(obj)).decode("ascii")}

    if isinstance(obj, Path):
        return str(obj)

    if isinstance(obj, (list, tuple, set)):
        return [ensure_jsonable(x, _depth + 1) for x in list(obj)]

    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        try:
            return obj.isoformat()
        except Exception:
            return repr(obj)

    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[str(k)] = ensure_jsonable(v, _depth + 1)
        return out

    if isinstance(obj, BaseException):
        return {"__exc__": obj.__class__.__name__, "msg": str(obj)}

    return repr(obj)

def dumps_safe(obj: Any, ensure_ascii: bool = False, **kwargs: Any) -> str:
    """先清洗再 json.dumps；預設不轉義非 ASCII。"""
    cleaned = ensure_jsonable(obj)
    return json.dumps(cleaned, ensure_ascii=ensure_ascii, separators=(",", ":"), default=str, **kwargs)

def dump_safe(obj: Any, path: str | Path, ensure_ascii: bool = False, **kwargs: Any) -> str:
    """將物件安全序列化後寫入檔案，回傳寫入的路徑字串。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    s = dumps_safe(obj, ensure_ascii=ensure_ascii, **kwargs)
    p.write_text(s, encoding="utf-8")
    return str(p)

# ---- 兼容別名（給舊碼/第三方測試用）----
to_jsonable = ensure_jsonable
json_dumps = dumps_safe
dumps = dumps_safe
dump = dump_safe
