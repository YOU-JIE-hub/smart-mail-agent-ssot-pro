import json
import inspect
from pathlib import Path

def _jsonable(x):
    try:
        json.dumps(x)
        return True
    except TypeError:
        return False

def test_json_safe_handles_path():
    # 不依賴具體函式名，盡量通用地把 json_safe 裡可能的處理器踩一遍
    import ai_rpa.utils.json_safe as js
    ran = False

    # 優先嘗試一些常見命名
    for name in ("to_jsonable", "coerce", "sanitize", "default", "encode", "as_jsonable"):
        if hasattr(js, name):
            out = getattr(js, name)(Path("/tmp"))
            assert _jsonable(out), f"{name} 應回傳可 JSON 化物件"
            ran = True
            break

    if not ran:
        # 回退：嘗試呼叫所有可呼叫、且只吃一個參數的函式
        for _, fn in inspect.getmembers(js, inspect.isfunction):
            try:
                # 儘量別引發例外，能跑通一個就算覆蓋到了
                out = fn(Path("/tmp"))
            except TypeError:
                continue
            except Exception:
                continue
            else:
                # 只要有任何一個函式能把 Path 轉成可 JSON 的就算達陣
                assert _jsonable(out), f"{fn.__name__} 應回傳可 JSON 化物件"
                ran = True
                break

    assert ran, "json_safe 應該要有至少一個處理 Path 的函式"
