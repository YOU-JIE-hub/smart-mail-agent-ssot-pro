#!/usr/bin/env python3
import argparse, json, pickle, re, os, sys, numpy as np
from pathlib import Path
from scipy.sparse import hstack, csr_matrix
from sklearn.metrics import classification_report, confusion_matrix
def rx(texts, srcs):
    regs=[re.compile(p,re.I) for p in srcs]
    return csr_matrix(np.array([[1 if r.search(t) else 0 for r in regs] for t in texts], dtype=np.float32))
def pick_model(m):
    if m: return m
    for p in ["artifacts/intent_svm_plus_best.pkl",
              "artifacts/intent_svm_plus_auto_cal.pkl",
              "artifacts/intent_svm_plus_auto.pkl",
              "artifacts/intent_svm_plus_split.pkl"]:
        if os.path.exists(p): return p
    return None
ap=argparse.ArgumentParser()
ap.add_argument("--model")
ap.add_argument("--input", required=True)
ap.add_argument("--errors_out")  # 可選：輸出誤分類檔
args=ap.parse_args()
model = pick_model(args.model)
if not model or not os.path.exists(model): print("[FAIL] model not found", file=sys.stderr) or sys.exit(2)
if not os.path.exists(args.input): print(f"[FAIL] input not found: {args.input}", file=sys.stderr) or sys.exit(2)
bundle = pickle.load(open(model,"rb"))
rows=[]; bad=0
with open(args.input,"r",encoding="utf-8",errors="replace") as f:
    for ln in f:
        ln=ln.strip()
        if not ln: continue
        try:
            r=json.loads(ln); 
            if not isinstance(r.get("text"), str) or not r["text"].strip(): bad+=1; continue
            rows.append(r)
        except Exception: bad+=1
if not rows: print("[FAIL] no valid rows", file=sys.stderr) or sys.exit(4)
texts=[r["text"] for r in rows]
X=hstack([bundle["char_vec"].transform(texts),
          bundle["word_vec"].transform(texts),
          rx(texts, bundle["regex_sources"])])
clf=bundle["clf"]; labels=clf.classes_.tolist()
pred=clf.predict(X)
has_y = all(("label" in r) for r in rows)
if has_y:
    y=[r["label"] for r in rows]
    print(classification_report(y, pred, labels=labels, digits=3, zero_division=0))
    cm=confusion_matrix(y, pred, labels=labels)
    print("[CONFUSION]"); print("\t"+"\t".join(labels))
    for i,row in enumerate(cm): print(labels[i]+"\t"+"\t".join(map(str,row)))
    if args.errors_out:
        with open(args.errors_out,"w",encoding="utf-8") as f:
            for r,yy,pp in zip(rows,y,pred):
                if yy!=pp: f.write(json.dumps({"id":r.get("id"),"text":r["text"],"gold":yy,"pred":pp},ensure_ascii=False)+"\n")
else:
    for r,yhat in zip(rows,pred):
        print(json.dumps({"id":r.get("id"),"text":r["text"],"pred":yhat}, ensure_ascii=False))
