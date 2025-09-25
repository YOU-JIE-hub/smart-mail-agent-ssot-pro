from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import json

_SPEC_PATH = Path("artifacts_prod/intent_feature_spec.json")

def _load_spec():
    if _SPEC_PATH.exists():
        try:
            return json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    # default spec（先給 0，校準工具會自動修正）
    return {"dims": {"prio": 0, "bias": 0}}

def rules_feat(X: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    """
    訓練期若用 DictVectorizer，這裡只需維持「鍵集合穩定」即可。
    我們回傳空 dict（等效全零），因為 DictVectorizer 的 vocabulary_ 已固定在模型裡。
    你也可以依需求填入規則特徵鍵值。
    """
    return [{} for _ in X]

def prio_feat(X: List[Dict[str, Any]]):
    try:
        import numpy as np
    except Exception:
        # 沒 numpy 就回傳 Python list（但 sklearn 多半會要 ndarray，建議安裝 numpy）
        d = _load_spec()["dims"].get("prio", 0)
        return [[0.0]*d for _ in X]
    d = _load_spec()["dims"].get("prio", 0)
    return np.zeros((len(X), d), dtype="float32")

def bias_feat(X: List[Dict[str, Any]]):
    try:
        import numpy as np
    except Exception:
        d = _load_spec()["dims"].get("bias", 0)
        return [[0.0]*d for _ in X]
    d = _load_spec()["dims"].get("bias", 0)
    return np.zeros((len(X), d), dtype="float32")
