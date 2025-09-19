import os, json, pathlib
from typing import List, Dict, Any

def _read_docs(kb_dir:str):
    kb = pathlib.Path(kb_dir)
    docs=[]
    for p in kb.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".md",".txt"}:
            try:
                docs.append({"id":str(p.relative_to(kb)), "text":p.read_text(encoding="utf-8", errors="ignore")})
            except Exception:
                pass
    return docs

def kb_search(query:str, kb_dir:str, k:int=3)->List[Dict[str,Any]]:
    docs = _read_docs(kb_dir)
    if not docs: return []
    # prefer sentence-transformers, else TF-IDF
    try:
        from sentence_transformers import SentenceTransformer, util
        m = SentenceTransformer("all-MiniLM-L6-v2")
        qv = m.encode([query], convert_to_tensor=True, normalize_embeddings=True)
        dv = m.encode([d["text"] for d in docs], convert_to_tensor=True, normalize_embeddings=True)
        scores = util.cos_sim(qv, dv).tolist()[0]
        rank = sorted(zip(docs, scores), key=lambda x:x[1], reverse=True)[:k]
        return [{"doc_id":d["id"], "score":float(s), "snippet":d["text"][:800]} for d,s in rank]
    except Exception:
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np
        corpus = [d["text"] for d in docs]
        vec = TfidfVectorizer().fit(corpus+[query])
        qv = vec.transform([query])
        dv = vec.transform(corpus)
        scores = (dv @ qv.T).toarray().ravel()
        idx = np.argsort(scores)[::-1][:k]
        return [{"doc_id":docs[i]["id"], "score":float(scores[i]), "snippet":docs[i]["text"][:800]} for i in idx]

def llm_generate(prompt:str, fallback:str)->str:
    prov = os.getenv("SMA_LLM_PROVIDER","none").lower()
    if prov in {"openai","azureopenai"} and os.getenv("OPENAI_API_KEY",""):
        try:
            import openai
            client = openai.OpenAI()
            r = client.chat.completions.create(model=os.getenv("SMA_LLM_MODEL","gpt-4o-mini"),
                                               messages=[{"role":"user","content":prompt}],
                                               temperature=float(os.getenv("SMA_LLM_T","0.3")))
            return (r.choices[0].message.content or "").strip()
        except Exception:
            pass
    return fallback

def render_with_citations(answer:str, hits:List[Dict[str,Any]])->str:
    if not hits: return answer
    foot = ["References:"]
    for i,h in enumerate(hits,1):
        foot.append(f"[#{i}] {h['doc_id']} (score={h['score']:.3f})")
    return answer + "\n\n" + "\n".join(foot)

def write_json(path, obj):
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
