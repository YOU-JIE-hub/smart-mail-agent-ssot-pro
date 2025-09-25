import json, inspect
from pathlib import Path
import ai_rpa.utils.json_safe as js

CASES = [Path("/tmp"), b"\x01\x02", {1,2}]

def _jsonable(x):
    try:
        json.dumps(x); return True
    except TypeError:
        return False

def test_json_safe_has_convertor_and_handles_common_types():
    names = ["to_jsonable","coerce","sanitize","default","encode","as_jsonable"]
    fns = [getattr(js, n) for n in names if hasattr(js, n) and callable(getattr(js, n))]
    if not fns:
        for _, fn in inspect.getmembers(js, inspect.isfunction):
            try:
                sig = inspect.signature(fn)
                req = [p for p in sig.parameters.values()
                       if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
                if len(req) == 1:
                    fns.append(fn)
            except Exception:
                continue
    assert fns, "json_safe 應至少暴露 1 個轉換器"

    ran = False
    for fn in fns:
        outs = []
        ok = True
        for v in CASES:
            try:
                outs.append(fn(v))
            except Exception:
                ok = False; break
        if ok and all(_jsonable(o) for o in outs):
            ran = True
            break
    assert ran, "至少一個轉換器可處理 Path/bytes/set 並回傳可 JSON 化物件"
