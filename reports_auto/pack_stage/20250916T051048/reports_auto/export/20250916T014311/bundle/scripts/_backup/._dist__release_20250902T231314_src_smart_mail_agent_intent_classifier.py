#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/intent/classifier.py
# 模組用途
#   載入 joblib 模型並以 labels.to_canonical 對齊輸出（若無模型，回傳 other）。
from __future__ import annotations

from pathlib import Path

from .labels import to_canonical
from .shim import ensure_joblib_main_shims

try:
    import joblib  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore
    joblib = None  # type: ignore

CATS = ["biz_quote", "tech_support", "complaint", "policy_qa", "profile_update", "other"]


def _probas(est, text: str) -> tuple[list[str], np.ndarray]:  # type: ignore[name-defined]
    if est is not None and hasattr(est, "predict_proba") and np is not None:
        p = np.asarray(est.predict_proba([text])[0], dtype=float)  # type: ignore[call-arg]
    else:
        # 模型缺失 → 直接 other
        import numpy as _np  # type: ignore

        p = _np.zeros((len(CATS),), dtype=float)
        p[-1] = 1.0
    labels = getattr(est, "classes_", None)
    if labels is None:
        labels = CATS
    if hasattr(labels, "tolist"):
        labels = labels.tolist()
    return list(labels), p  # type: ignore[return-value]


class IntentRouter:
    """參數: root；回傳: predict(text)->label。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        ensure_joblib_main_shims()
        self.model = self._load()

    def _load(self):
        if joblib is None:
            return None
        try:
            mp = self.root / "artifacts" / "intent_pro_cal.pkl"
            if mp.exists():
                return joblib.load(mp)
        except Exception:
            return None
        return None

    def predict(self, text: str) -> str:
        labels, p = _probas(self.model, text)
        order = {str(lbl): i for i, lbl in enumerate(labels)}
        import numpy as _np  # type: ignore

        vec = _np.zeros((len(CATS),), dtype=float)
        for i, lbl in enumerate(CATS):
            if lbl in order:
                vec[i] = float(p[order[lbl]])
        k = int(_np.argmax(vec))
        p1 = float(vec[k])
        lbl = CATS[k]
        # 門檻（若模型不存在，多半會是 other）
        cut = 0.5
        return to_canonical(lbl if p1 >= cut else "other")
