#!/usr/bin/env python3
import argparse, json, pickle, re
from pathlib import Path
import numpy as np
from scipy.sparse import hstack, csr_matrix

def featurize_regex(texts, rx_srcs):
    regs=[re.compile(p, re.I) for p in rx_srcs]
    return csr_matrix(np.array([[1 if rx.search(t) else 0 for rx in regs] for t in texts], dtype=np.float32))

def load_bundle(p:Path):
    with p.open("rb") as f: return pickle.load(f)

# import helpers
import importlib.util
spec = importlib.util.spec_from_file_location("extract_fields", ".sma_tools/extract_fields.py")
m1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m1)
extract_fields = m1.extract_fields

spec2 = importlib.util.spec_from_file_location("priority_rules", ".sma_tools/priority_rules.py")
m2 = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(m2)
classify_priority = m2.classify_priority

def predict(rows, bundle):
    texts=[r["text"] for r in rows]
    Xc=bundle["char_vec"].transform(texts)
    Xw=bundle["word_vec"].transform(texts)
    Xr=featurize_regex(texts,bundle["regex_sources"])
    X=hstack([Xc,Xw,Xr])
    clf=bundle["clf"]; labels=clf.classes_.tolist()
    margins=clf.decision_function(X)
    if margins.ndim==1: margins=margins.reshape(-1,1)
    e=np.exp(margins - margins.max(axis=1, keepdims=True)); probs=e/e.sum(axis=1, keepdims=True)
    idx=np.argmax(probs,axis=1)
    out=[]
    for i,r in enumerate(rows):
        t=r["text"]; f=extract_fields(t); pr=classify_priority(t,f)
        out.append({"id":r.get("id"),"text":t,"intent":labels[int(idx[i])],"confidence":float(probs[i,int(idx[i])]),
                    "fields":f,"priority":pr["priority"],"priority_reason":pr["reason"]})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model", default="artifacts/intent_svm_plus_auto.pkl")
    ap.add_argument("--input", required=True)   # JSONL of {id?, text}
    ap.add_argument("--output", required=True)  # JSONL of predictions
    args=ap.parse_args()
    bundle=load_bundle(Path(args.model))
    rows=[]
    with open(args.input,"r",encoding="utf-8") as f:
        for ln in f:
            if ln.strip(): rows.append(json.loads(ln))
    preds=predict(rows,bundle)
    with open(args.output,"w",encoding="utf-8") as f:
        for p in preds: f.write(json.dumps(p, ensure_ascii=False)+"\n")
if __name__=="__main__": main()
