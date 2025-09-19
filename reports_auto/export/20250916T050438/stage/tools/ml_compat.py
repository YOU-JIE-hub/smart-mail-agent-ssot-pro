
from __future__ import annotations
import sys, importlib
from pathlib import Path
from typing import Any

def alias_main()->bool:
    # 先找 src.sma_features，再找 sma_features
    for name in ("src.sma_features", "sma_features"):
        try:
            mod = importlib.import_module(name)
            sys.modules["__main__"] = mod  # 舊 pickle 會到 __main__ 找 rules_feat / prio_feat / bias_feat
            return True
        except Exception:
            pass
    return False

def joblib_load(path: str|Path)->Any:
    alias_main()
    import joblib
    return joblib.load(Path(path))

def find_estimator(obj: Any)->Any|None:
    if hasattr(obj, "predict"): return obj
    if isinstance(obj, dict):
        for k in ("model","pipeline","clf","estimator","pipe","sk_model"):
            v = obj.get(k)
            if hasattr(v, "predict"): return v
        for v in obj.values():
            if hasattr(v, "predict"): return v
    return None
