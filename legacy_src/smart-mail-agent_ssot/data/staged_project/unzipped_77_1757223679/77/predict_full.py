#!/usr/bin/env python3
import argparse,sys,json,re,pickle
from pathlib import Path
import numpy as np
from scipy.sparse import hstack,csr_matrix

def featurize_regex(texts, rx_srcs):
    regs=[re.compile(p, re.I) for p in rx_srcs]
    return csr_matrix(np.array([[1 if rx.search(t) else 0 for rx in regs] for t in texts], dtype=np.float32))

def load_bundle(p:Path):
    with p.open("rb") as f: return pickle.load(f)

import importlib.util
spec = importlib.util.spec_from_file_location("extract_fields", ".sma_tools/extract_fields.py")
m1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m1)
extract_fields = m1.extract_fields
spec2 = importlib.util.spec_from_file_location("priority_rules", ".sma_tools/priority_rules.py")
m2 = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(m2)
classify_priority = m2.classify_priority

def predict_texts(texts,bundle):
    Xc=bundle["char_vec"].transform(texts)
    Xw=bundle["word_vec"].transform(texts)
    Xr=featurize_regex(texts,bundle["regex_sources"])
    X=hstack([Xc,Xw,Xr])
    if "cal" in bundle:
        cal=bundle["cal"]; probs=cal.predict_proba(X); labels=cal.classes_.tolist()
    else:
        clf=bundle["clf"]; labels=clf.classes_.tolist()
        margins=clf.decision_function(X)
        if margins.ndim==1: margins=margins.reshape(-1,1)
        e=np.exp(margins-margins.max(axis=1,keepdims=True)); probs=e/e.sum(axis=1,keepdims=True)
    idx=np.argmax(probs,axis=1)
    out=[]
    for i,t in enumerate(texts):
        fields=extract_fields(t); pri=classify_priority(t,fields)
        out.append({"text":t,"intent":labels[int(idx[i])],"confidence":float(probs[i,int(idx[i])]),
                    "fields":fields,"priority":pri["priority"],"priority_reason":pri["reason"]})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model", default="artifacts/intent_svm_plus_auto.pkl")
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text"); g.add_argument("--input")
    args=ap.parse_args()
    bundle=load_bundle(Path(args.model))
    if args.text:
        print(json.dumps(predict_texts([args.text],bundle)[0], ensure_ascii=False))
    else:
        rows=[json.loads(ln) for ln in Path(args.input).read_text(encoding="utf-8").splitlines() if ln.strip()]
        for r in predict_texts([row["text"] for row in rows],bundle):
            print(json.dumps(r, ensure_ascii=False))
if __name__=="__main__": main()
