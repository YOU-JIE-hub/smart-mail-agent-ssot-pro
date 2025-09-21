import json, re, pickle, os
from pathlib import Path
import numpy as np
from scipy.sparse import hstack, csr_matrix

ROOT=Path(".")
HOLD=ROOT/"data/intent/external_holdout.jsonl"
REP=ROOT/"reports_auto"
REP.mkdir(parents=True, exist_ok=True)

def rx(texts,srcs):
    regs=[re.compile(p,re.I) for p in srcs]
    mat=[[1 if r.search(t) else 0 for r in regs] for t in texts]
    return csr_matrix(np.array(mat,dtype=np.float32))

def load_bundle(p):
    with open(p,"rb") as f: return pickle.load(f)

def pick_model():
    a="artifacts/intent_svm_plus_auto_cal.pkl"
    b="artifacts/intent_svm_plus_auto.pkl"
    return a if Path(a).exists() else b

if not HOLD.exists():
    raise SystemExit("[MISS] holdout not found. run make_holdout.py first")

model=pick_model()
b=load_bundle(model)
rows=[json.loads(x) for x in HOLD.read_text(encoding="utf-8").splitlines() if x.strip()]
Xc=b["char_vec"].transform([r["text"] for r in rows])
Xw=b["word_vec"].transform([r["text"] for r in rows])
Xr=rx([r["text"] for r in rows], b["regex_sources"])
X=hstack([Xc,Xw,Xr])
clf=b["clf"]; labels=clf.classes_.tolist()
pred=clf.predict(X)

miss=[]
for r,yh in zip(rows,pred):
    if "label" in r and r["label"]!=yh:
        miss.append({"id":r.get("id"),"text":r["text"],"gold":r["label"],"pred":yh})

(Path(REP/"holdout_misses.jsonl")).write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in miss)+"\n",encoding="utf-8")
print("[MISS_CNT]", len(miss), "->", REP/"holdout_misses.jsonl")
