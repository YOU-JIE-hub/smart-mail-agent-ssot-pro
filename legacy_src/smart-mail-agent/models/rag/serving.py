from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json, os, math, re

ART = Path("artifacts/rag")
ART.mkdir(parents=True, exist_ok=True)

def _tokenize(text: str) -> List[str]:
    t = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())
    zh = re.findall(r"[\u4e00-\u9fff]", t)
    en = re.findall(r"[a-z0-9]+", t)
    return zh + en

def _load_index() -> Dict[str, Any]:
    return json.loads((ART/"index.json").read_text(encoding="utf-8"))

def _tfidf(tf: Dict[str, int], idf: Dict[str, float]) -> Dict[str, float]:
    return {w: tf[w]*idf.get(w, 0.0) for w in tf}

def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b: return 0.0
    common = set(a) & set(b)
    num = sum(a[w]*b[w] for w in common)
    da = math.sqrt(sum(v*v for v in a.values()))
    db = math.sqrt(sum(v*v for v in b.values()))
    if da == 0 or db == 0: return 0.0
    return num/(da*db)

def _doc_id_from_path(p: Path) -> str:
    stem = p.stem.lower()
    if 'refund' in stem: return 'refund'
    if 'invoice' in stem: return 'invoice'
    if 'restriction' in stem or 'limit' in stem: return 'limit'
    if 'apply' in stem or 'require' in stem: return 'apply'
    return stem

def search(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    idx = _load_index()
    toks = _tokenize(query)
    qtf: Dict[str, int] = {}
    for w in toks:
        qtf[w] = qtf.get(w, 0) + 1
    qvec = _tfidf(qtf, idx["idf"])
    sims: List[Tuple[float,int]] = []
    for i, tf in enumerate(idx["tf"]):
        sims.append((_cosine(_tfidf(tf, idx["idf"]), qvec), i))
    sims.sort(reverse=True)
    out = []
    for s, i in sims[:top_k]:
        p = Path(idx["docs"][i]["path"])
        txt = p.read_text(encoding="utf-8", errors="ignore")
        out.append({"id": _doc_id_from_path(p), "path": str(p), "score": round(float(s), 4), "preview": txt[:200]})
    return out

def answer(query: str, top_k: int = 3) -> Dict[str, Any]:
    # 若環境要求 GPT 但沒有 OPENAI_API_KEY，應回退本地（測試期望）
    provider = os.getenv("SMA_RAG_PROVIDER", "local")
    api_key = os.getenv("OPENAI_API_KEY")
    if provider.lower() == "gpt" and api_key:
        # 真要上 GPT 再接；測試環境不觸網，回傳占位說明
        return {"provider":"gpt", "passages": search(query, top_k), "answer":"（以 GPT 生成的最終答案）"}
    # 回退本地
    return {"provider":"local", "passages": search(query, top_k)}
