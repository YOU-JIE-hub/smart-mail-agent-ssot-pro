from __future__ import annotations
from pathlib import Path
import argparse, json, re, math

def tokenize(s: str) -> list[str]:
    try:
        import regex as rx
        return [t.lower() for t in rx.findall(r'\p{L}[\p{L}\p{M}\p{N}_]*|\p{N}+', s)]
    except Exception:
        return [t.lower() for t in re.findall(r'\w+', s, flags=re.UNICODE)]

def load_index(index_path: Path):
    if index_path.exists():
        try:
            return json.loads(index_path.read_text("utf-8"))
        except Exception:
            return None
    return None

def bm25_score(query_tokens, index, k1=1.5, b=0.75):
    # 前置
    N = index["N"]; df = index["df"]; docs=index["docs"]; avgdl = index["avgdl"] or 1.0
    q_terms = {}
    for t in query_tokens: q_terms[t]=q_terms.get(t,0)+1
    scores={}
    for doc_id, di in docs.items():
        dl= di["len"] or 1
        s=0.0
        for t in q_terms:
            tf = di["tf"].get(t,0)
            if tf==0: continue
            dft = df.get(t,0)
            idf = math.log(1 + (N - dft + 0.5) / (dft + 0.5)) if dft>0 else math.log(1 + (N + 0.5)/0.5)
            denom = tf + k1*(1 - b + b*dl/avgdl)
            s += idf * tf * (k1 + 1) / denom
        if s>0: scores[doc_id]=s
    # 構造 hit 結果
    hits=[]
    for doc_id, sc in sorted(scores.items(), key=lambda x: -x[1]):
        di = docs[doc_id]
        hits.append({"file": doc_id, "title": di.get("title",""), "score": float(sc), "snippet": di.get("snippet","")})
    return hits

def naive_search(query:str, kb_dir:str, topk:int):
    # 舊的 overlap 退路
    docs=[]
    for p in sorted(Path(kb_dir).rglob("*")):
        if p.is_file() and p.suffix.lower() in {".md",".txt"}:
            txt=p.read_text("utf-8", errors="ignore")
            tit=txt.splitlines()[0].lstrip("# ").strip() if txt.strip() else p.stem
            docs.append((p.name, tit, txt))
    q=set(tokenize(query)); 
    scored=[]
    for f,tit,txt in docs:
        t=set(tokenize(txt)); 
        inter=len(q & t); 
        if inter>0:
            scored.append({"file":f,"title":tit,"score":inter,"snippet":(txt[:240].replace("\n"," ")+"…")})
    scored.sort(key=lambda x:-x["score"])
    return scored[:topk]

def search(query: str, kb_dir: str, topk: int = 3) -> list[dict]:
    idx = load_index(Path("kb/index.json"))
    if idx and idx.get("N",0)>0:
        return bm25_score(tokenize(query), idx)[:topk]
    return naive_search(query, kb_dir, topk)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--kb-dir", default="kb/faq")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--out")
    a=ap.parse_args()
    hits = search(a.query, a.kb_dir, a.topk)
    s = json.dumps({"query": a.query, "hits": hits}, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(s, "utf-8")
        print(f"[OK] kb hits -> {a.out}  topk={len(hits)}")
    else:
        print(s)

if __name__=="__main__":
    main()
