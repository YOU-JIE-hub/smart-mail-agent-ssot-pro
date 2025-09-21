from __future__ import annotations
import math, re
from pathlib import Path
from collections import Counter, defaultdict

def _tokenize(s:str):
    return re.findall(r"[A-Za-z0-9\u4e00-\u9fa5]+", (s or "").lower())

def _docs(kb_dir="kb/faq"):
    docs=[]
    for p in Path(kb_dir).glob("*.md"):
        txt=p.read_text(encoding="utf-8", errors="ignore")
        docs.append((str(p), txt))
    return docs

def retrieve(query:str, topk:int=5, kb_dir="kb/faq"):
    q=_tokenize(query); if not q: return []
    docs=_docs(kb_dir); N=len(docs); 
    df=defaultdict(int); tfs=[]
    for _,txt in docs:
        toks=_tokenize(txt); c=Counter(toks); tfs.append(c)
        for w in set(toks): df[w]+=1
    def idf(w): 
        return math.log((N - df.get(w,0) + 0.5) / (df.get(w,0) + 0.5) + 1)
    scores=[]
    for i,(pid,txt) in enumerate(docs):
        s=0.0; c=tfs[i]
        for w in q: s += idf(w)*c.get(w,0)
        scores.append((s, pid, txt[:800]))
    scores.sort(reverse=True)
    return scores[:topk]
