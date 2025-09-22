from __future__ import annotations
import json, re, pickle
from pathlib import Path
from typing import Tuple

_DEFAULT_TH = 0.44
_BLACKLIST = [
    r"free money", r"viagra", r"winner", r"crypto pump",
    r"click here", r"limited time", r"investment opportunity",
]

class SpamGuard:
    def __init__(self,
                 model_path: Path = Path("artifacts_prod/model_pipeline.pkl"),
                 th_path: Path = Path("artifacts_prod/ens_thresholds.json")):
        self.model_path = model_path
        self.th_path = th_path
        self.model = None
        self.threshold = _DEFAULT_TH
        self._load()

    def _load(self) -> None:
        try:
            if self.th_path.exists():
                data = json.loads(self.th_path.read_text(encoding="utf-8"))
                self.threshold = float(
                    data.get("threshold")
                    or data.get("best_f1")
                    or (data.get("global") or {}).get("threshold")
                    or _DEFAULT_TH
                )
        except Exception:
            self.threshold = _DEFAULT_TH
        try:
            import sklearn  # noqa: F401
            if self.model_path.exists():
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
        except Exception:
            self.model = None

    def predict_proba(self, text: str) -> float:
        if self.model is not None:
            try:
                proba = self.model.predict_proba([text])[0]
                if hasattr(proba, "__len__") and len(proba) == 2:
                    return float(proba[1])
                return float(max(proba))
            except Exception:
                pass
        low = text.lower()
        hits = sum(1 for p in _BLACKLIST if re.search(p, low))
        return min(0.99, 0.20 + 0.20 * hits)

    def is_spam(self, text: str) -> Tuple[bool, float, float]:
        p = self.predict_proba(text)
        return (p >= self.threshold, p, self.threshold)
