from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json, math, re, os

ART_DIR = Path("artifacts/rag")
ART_DIR.mkdir(parents=True, exist_ok=True)
INDEX_PATH = ART_DIR / "index.json"
KNOW_DIR = Path("knowledge")
KNOW_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DOCS = [
    {
        "id": "refund_policy",
        "title": "退款機制",
        "text": "可於購買後 7 天內申請退款。需提供訂單編號與原因。退款將以原支付方式退回。"
    },
    {
        "id": "usage_restrictions",
        "title": "使用限制",
        "text": "試用方案僅供個人用途。商用請聯絡業務取得正式授權與報價。"
    },
    {
        "id": "apply_requirements",
        "title": "申請條件",
        "text": "申請需年滿 18 歲並填寫完整資料。若需加值功能，需通過 KYC。"
    }
]

def _tokenize(text: str) -> List[str]:
    t = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())
    zh = re.findall(r"[\u4e00-\u9fff]", t)
    en = re.findall(r"[a-z0-9]+", t)
    return zh + en

def _write_default_knowledge():
    for d in DEFAULT_DOCS:
        p = KNOW_DIR / f"{d['id']}.txt"
        if not p.exists():
            p.write_text(d["title"] + "\n\n" + d["text"], encoding="utf-8")

def build(knowledge_dir: Path = KNOW_DIR, index_path: Path = INDEX_PATH) -> Dict[str, Any]:
    """
    掃描 knowledge_dir 下的 *.txt，建立簡單 TF-IDF 索引（不依賴第三方套件）。
    """
    _write_default_knowledge()
    docs = []
    for p in sorted(Path(knowledge_dir).glob("*.txt")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        docs.append({"id": p.stem, "path": str(p), "text": text})
    if not docs:
        raise RuntimeError("No knowledge docs found")

    # 詞頻
    term_df: Dict[str, int] = {}
    doc_tf: List[Dict[str, int]] = []
    for d in docs:
        toks = _tokenize(d["text"])
        tf: Dict[str, int] = {}
        for w in toks:
            tf[w] = tf.get(w, 0) + 1
        doc_tf.append(tf)
        for w in set(toks):
            term_df[w] = term_df.get(w, 0) + 1

    N = len(docs)
    idf = {w: math.log((N + 1) / (df + 1)) + 1 for w, df in term_df.items()}
    # 寫 index
    index = {
        "docs": [{"id": d["id"], "path": d["path"]} for d in docs],
        "idf": idf,
        "tf": doc_tf,
    }
    Path(index_path).parent.mkdir(parents=True, exist_ok=True)
    Path(index_path).write_text(json.dumps(index), encoding="utf-8")
    return {"ok": True, "index_path": str(index_path), "num_docs": N}

def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b: return 0.0
    common = set(a) & set(b)
    num = sum(a[w] * b[w] for w in common)
    da = math.sqrt(sum(v*v for v in a.values()))
    db = math.sqrt(sum(v*v for v in b.values()))
    if da == 0 or db == 0: return 0.0
    return num / (da * db)

def _tfidf(tf: Dict[str, int], idf: Dict[str, float]) -> Dict[str, float]:
    return {w: (tf[w] * idf.get(w, 0.0)) for w in tf.keys()}

def query(question: str, index_path: Path = INDEX_PATH, top_k: int = 3) -> Dict[str, Any]:
    idx = json.loads(Path(index_path).read_text(encoding="utf-8"))
    toks = _tokenize(question)
    qtf: Dict[str, int] = {}
    for w in toks:
        qtf[w] = qtf.get(w, 0) + 1
    qvec = _tfidf(qtf, idx["idf"])
    # 對每個文件算 cosine
    sims: List[Tuple[float, int]] = []
    for i, tf in enumerate(idx["tf"]):
        sims.append(( _cosine(_tfidf(tf, idx["idf"]), qvec), i ))
    sims.sort(reverse=True)
    top = sims[:top_k]
    docs = []
    for s, i in top:
        path = idx["docs"][i]["path"]
        txt = Path(path).read_text(encoding="utf-8", errors="ignore")
        docs.append({"path": path, "score": round(float(s), 4), "preview": txt[:200]})
    # 若有 OPENAI_API_KEY 可組合生成，否則回傳拼接摘要（不對外網）
    if os.getenv("OPENAI_API_KEY"):
        answer = "（此處可接 GPT API 進一步生成回答；測試環境將不調用外網）"
    else:
        answer = " / ".join(d["preview"].splitlines()[0] for d in docs if d["preview"])
    return {"question": question, "top_docs": docs, "answer": answer}

if __name__ == "__main__":
    info = build()
    q = query("退款機制與使用限制")
    print(json.dumps({"ok": True, "index": info, "qa": q}, ensure_ascii=False))
