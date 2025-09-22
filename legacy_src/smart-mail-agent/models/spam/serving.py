from __future__ import annotations
from pathlib import Path
import json
from typing import Dict, List
from models.common import tokenize

ART = Path(__file__).resolve().parent/"artifacts"

def _load():
    p = ART/"model.json"
    if not p.exists():
        return {"spam_keywords":["free","money","btc","bitcoin","usdt","空投","返利","viagra"], "threshold":0.5}
    return json.loads(p.read_text(encoding="utf-8"))

def score(texts: List[str]) -> Dict[str, float|str]:
    m = _load()
    kws = set(m["spam_keywords"])
    total = 0; hits = 0
    for t in texts:
        toks = set(tokenize(t))
        if kws & toks:
            hits += 1
        total += 1
    conf = hits / max(1,total)
    return {"label": "spam" if conf >= m.get("threshold",0.5) else "ham", "score": float(conf)}
