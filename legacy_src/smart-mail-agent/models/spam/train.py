from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional
import json, re

ART_DIR = Path("artifacts/spam")
ART_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = ART_DIR / "spam_rules.json"

DEFAULT_SPAM_WORDS = [
    "free money","bitcoin","btc","usdt","viagra","空投","返利","暴富","大額補貼","快速致富"
]
DEFAULT_HAM_HINTS = ["合作","報價","客服","退款","發票","支援","條款","申請"]

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())

def train(spam_words: Optional[List[str]] = None,
          ham_hints: Optional[List[str]] = None,
          out_path: Path = MODEL_PATH) -> Dict[str, Any]:
    model = {
        "spam_words": list(set(spam_words or DEFAULT_SPAM_WORDS)),
        "ham_hints": list(set(ham_hints or DEFAULT_HAM_HINTS)),
        "thresholds": {"adapter_block": 0.5}  # 與 mailguard 門檻一致
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    return model

def load(path: Path = MODEL_PATH) -> Dict[str, Any]:
    if not Path(path).exists():
        return train(out_path=path)
    return json.loads(Path(path).read_text(encoding="utf-8"))

def score(text: str, model: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    m = model or load()
    t = _normalize(text)
    hits = [w for w in m["spam_words"] if w in t]
    anti = [h for h in m["ham_hints"] if h in t]
    raw = len(hits) - 0.3*len(anti)
    # 轉為 0~1 sigmoid-like
    s = 1 - (1 / (1 + max(raw, 0)))
    label = "spam" if s >= m["thresholds"]["adapter_block"] else "ham"
    return {"label": label, "score": float(round(s, 4)), "hits": hits, "anti": anti, "threshold": m["thresholds"]["adapter_block"]}

if __name__ == "__main__":
    m = train()
    print(json.dumps({"ok": True, "artifact": str(MODEL_PATH), "score_example": score("free money!!!", m)}, ensure_ascii=False))
