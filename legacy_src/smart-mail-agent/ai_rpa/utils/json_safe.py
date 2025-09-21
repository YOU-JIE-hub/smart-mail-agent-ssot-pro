from __future__ import annotations
import json, math, datetime as _dt
from pathlib import Path
from decimal import Decimal

__all__ = ["jsonable"]

def _to_plain(x):
    if x is None or isinstance(x,(bool,int,float,str)):
        if isinstance(x,float) and (math.isnan(x) or math.isinf(x)): return None
        return x
    if isinstance(x,Decimal):
        try: return float(x)
        except Exception: return str(x)
    if isinstance(x,(_dt.datetime,_dt.date)):
        return x.isoformat()
    if isinstance(x,(bytes,bytearray)):
        try: return x.decode("utf-8","ignore")
        except Exception: return f"<bytes:{len(x)}>"
    if isinstance(x,Path):
        return str(x)
    if isinstance(x,dict):
        return {str(k): _to_plain(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,set,frozenset)):
        return [_to_plain(i) for i in x]
    return str(x)

def jsonable(x):
    y = _to_plain(x)
    try:
        json.dumps(y)
        return y
    except Exception:
        return str(y)
def to_jsonable(x):
    try:
        from .json_safe import jsonable  # 自身別名
    except Exception:
        return x
    return jsonable(x)
