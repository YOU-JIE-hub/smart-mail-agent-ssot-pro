#!/usr/bin/env python3
import argparse, pathlib, json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

def load_docs(root):
    R=pathlib.Path(root); docs=[]
    for p in R.rglob("*"):
        if p.suffix.lower() in (".md",".txt",".html",".json"):
            try: docs.append({"id":str(p), "text":p.read_text(encoding="utf-8",errors="ignore")})
            except: pass
    return docs

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--faq_dir', default='data/faq')
    ap.add_argument('--query', required=True)
    ap.add_argument('--topk', type=int, default=3)
    a=ap.parse_args()
    D=load_docs(a.faq_dir)
    if not D: print(json.dumps({'hits':[]},ensure_ascii=False)); raise SystemExit(0)
    vec=TfidfVectorizer(ngram_range=(1,2),max_df=0.9)
    X=vec.fit_transform([d['text'] for d in D]); qv=vec.transform([a.query])
    sim=linear_kernel(qv,X).ravel(); idx=sim.argsort()[::-1][:a.topk]
    hits=[{'doc':D[i]['id'],'score':float(sim[i]),'snippet':D[i]['text'][:800]} for i in idx]
    print(json.dumps({'hits':hits}, ensure_ascii=False))
