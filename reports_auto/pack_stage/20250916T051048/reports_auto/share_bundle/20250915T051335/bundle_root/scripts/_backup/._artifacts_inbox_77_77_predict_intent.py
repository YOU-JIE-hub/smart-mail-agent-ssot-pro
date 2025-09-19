#!/usr/bin/env python3
import argparse,sys,json,re,pickle
from pathlib import Path
import numpy as np
from scipy.sparse import hstack,csr_matrix

def featurize_regex(texts, rx_srcs):
    regs=[re.compile(p, re.I) for p in rx_srcs]
    mat=[[1 if rx.search(t) else 0 for rx in regs] for t in texts]
    return csr_matrix(np.array(mat,dtype=np.float32))

def load_bundle(p:Path):
    with p.open("rb") as f: return pickle.load(f)

def predict_texts(texts,bundle):
    Xc=bundle["char_vec"].transform(texts)
    Xw=bundle["word_vec"].transform(texts)
    Xr=featurize_regex(texts,bundle["regex_sources"])
    X=hstack([Xc,Xw,Xr])
    clf=bundle["clf"]
    labels=clf.classes_.tolist()
    margins=clf.decision_function(X)
    if margins.ndim==1: margins=margins.reshape(-1,1)
    e=np.exp(margins - margins.max(axis=1, keepdims=True))
    prob=e/ e.sum(axis=1, keepdims=True)
    idx=prob.argmax(axis=1)
    return [{"label":labels[i], "confidence":float(prob[j,i])} for j,i in enumerate(idx)]

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--model", default="artifacts/intent_svm_plus_boost.pkl")
    ap.add_argument("--text")
    ap.add_argument("--input")
    args=ap.parse_args()
    bundle=load_bundle(Path(args.model))
    inputs=[]
    if args.text: inputs=[args.text]
    elif args.input:
        with open(args.input,"r",encoding="utf-8") as f:
            for ln in f:
                if ln.strip(): inputs.append(ln.strip())
    else:
        for ln in sys.stdin:
            if ln.strip(): inputs.append(ln.strip())
    for t,p in zip(inputs, predict_texts(inputs,bundle)):
        print(json.dumps({"text":t[:80],"label":p["label"],"confidence":round(p["confidence"],3)}, ensure_ascii=False))
