#!/usr/bin/env python3
import argparse, json, pickle, re, time
from pathlib import Path
import numpy as np
from scipy.sparse import hstack, csr_matrix

def featurize_regex(texts, rx_srcs):
    regs=[re.compile(p, re.I) for p in rx_srcs]
    return csr_matrix(np.array([[1 if rx.search(t) else 0 for rx in regs] for t in texts], dtype=np.float32))

def load_bundle(p): 
    with open(p,"rb") as f: return pickle.load(f)

import importlib.util
spec1=importlib.util.spec_from_file_location("extract_fields",".sma_tools/extract_fields.py")
m1=importlib.util.module_from_spec(spec1); spec1.loader.exec_module(m1)
extract_fields=m1.extract_fields
spec2=importlib.util.spec_from_file_location("priority_rules",".sma_tools/priority_rules.py")
m2=importlib.util.module_from_spec(spec2); spec2.loader.exec_module(m2)
classify_priority=m2.classify_priority

def decide_route(intent,conf,priority,thres):
    t=thres.get(intent,0.5)
    if priority=="P1": return "escalate_oncall"
    if conf<t: return "human_review"
    return "auto"

def infer_probs(bundle, X):
    if "cal" in bundle:
        cal=bundle["cal"]; return cal.predict_proba(X), cal.classes_.tolist()
    clf=bundle["clf"]; labels=clf.classes_.tolist()
    margins=clf.decision_function(X)
    if margins.ndim==1: margins=margins.reshape(-1,1)
    e=np.exp(margins-margins.max(axis=1,keepdims=True)); probs=e/e.sum(axis=1,keepdims=True)
    return probs, labels

def predict_rows(rows,bundle,thres,collect_path=None):
    texts=[r["text"] for r in rows]
    Xc=bundle["char_vec"].transform(texts)
    Xw=bundle["word_vec"].transform(texts)
    Xr=featurize_regex(texts,bundle["regex_sources"])
    X=hstack([Xc,Xw,Xr])
    probs,labels=infer_probs(bundle,X)
    idx=np.argmax(probs,axis=1)
    out=[]
    low=[]
    for i,r in enumerate(rows):
        t=r["text"]; fields=extract_fields(t); pri=classify_priority(t,fields)
        intent=labels[int(idx[i])]; conf=float(probs[i,int(idx[i])])
        route=decide_route(intent,conf,pri["priority"],thres)
        o={"id":r.get("id"),"text":t,"intent":intent,"confidence":conf,
           "fields":fields,"priority":pri["priority"],"priority_reason":pri["reason"],
           "route":route}
        out.append(o)
        if route=="human_review":
            o2=dict(o); o2["ts"]=int(time.time()); low.append(o2)
    if collect_path and low:
        p=Path(collect_path); p.parent.mkdir(parents=True,exist_ok=True)
        with p.open("a",encoding="utf-8") as f:
            for o in low: f.write(json.dumps(o, ensure_ascii=False)+"\n")
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model")
    def pick_model():
        cal="artifacts/intent_svm_plus_auto_cal.pkl"
        base="artifacts/intent_svm_plus_auto.pkl"
        from pathlib import Path
        return cal if Path(cal).exists() else base
    ap.add_argument("--thresholds", default=".sma_tools/router_config.json")
    ap.add_argument("--collect-lowconf")
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text"); g.add_argument("--input")
    ap.add_argument("--output")
    args=ap.parse_args()
    thres={"biz_quote":0.55,"tech_support":0.50,"policy_qa":0.50,"profile_update":0.55,"complaint":0.50,"other":0.60}
    if Path(args.thresholds).exists():
        thres=json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
    bundle=load_bundle(args.model or pick_model())
    if args.text:
        rows=[{"text":args.text}]
        print(json.dumps(predict_rows(rows,bundle,thres,args.collect_lowconf)[0], ensure_ascii=False))
    else:
        rows=[]
        with open(args.input,"r",encoding="utf-8") as f:
            for ln in f:
                ln=ln.strip()
                if ln: rows.append(json.loads(ln))
        preds=predict_rows(rows,bundle,thres,args.collect_lowconf)
        if args.output:
            with open(args.output,"w",encoding="utf-8") as f:
                for p in preds: f.write(json.dumps(p, ensure_ascii=False)+"\n")
        else:
            for p in preds: print(json.dumps(p, ensure_ascii=False))
if __name__=="__main__": main()
