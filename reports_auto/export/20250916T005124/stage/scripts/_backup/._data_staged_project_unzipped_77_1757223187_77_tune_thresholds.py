#!/usr/bin/env python3
import json, os, pickle, numpy as np, re
from pathlib import Path
from sklearn.model_selection import StratifiedShuffleSplit
from scipy.sparse import hstack, csr_matrix
def rx(texts, srcs):
    regs=[re.compile(p,re.I) for p in srcs]
    return csr_matrix(np.array([[1 if r.search(t) else 0 for r in regs] for t in texts], dtype=np.float32))
def softmax_margins(M):
    M = np.array(M, dtype=np.float64)
    if M.ndim==1: M=M.reshape(1,-1)
    M = M - M.max(axis=1, keepdims=True)
    E = np.exp(M); P = E / E.sum(axis=1, keepdims=True)
    return P
ROOT=Path(".")
cfgp=ROOT/".sma_tools/router_config.json"
model=None
for p in ["artifacts/intent_svm_plus_best.pkl","artifacts/intent_svm_plus_auto_cal.pkl","artifacts/intent_svm_plus_auto.pkl"]:
    if Path(p).exists(): model=p; break
assert model, "no model"
B=pickle.load(open(model,"rb"))
def load_split():
    sp=ROOT/"data/intent_split_auto/val.jsonl"
    if sp.exists():
        import json
        rows=[json.loads(x) for x in sp.read_text(encoding="utf-8").splitlines() if x.strip()]
        return rows
    # fallback: rebuild and split
    def readj(p):
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
    MERG=ROOT/"data/intent/i_20250901_merged.jsonl"
    FULL=ROOT/"data/intent/i_20250901_full.jsonl"
    HC=ROOT/"data/intent/i_20250901_handcrafted_aug.jsonl"
    CB=ROOT/"data/intent/i_20250901_complaint_boost.jsonl"
    AUTO=ROOT/"data/intent/i_20250901_auto_aug.jsonl"
    rows=[]; seen=set()
    for p in [MERG,FULL,HC,CB,AUTO]:
        if p.exists():
            for ln in p.read_text(encoding="utf-8").splitlines():
                if not ln.strip(): continue
                r=json.loads(ln); t=r.get("text",""); lab=r.get("label")
                if not t or not lab: continue
                k=(lab, r.get("meta",{}).get("language"), t.lower())
                if k in seen: continue
                seen.add(k); rows.append(r)
    from sklearn.model_selection import StratifiedShuffleSplit
    X=[r["text"] for r in rows]; y=[r["label"] for r in rows]
    sss=StratifiedShuffleSplit(n_splits=1, test_size=0.1, random_state=20250901)
    idx_tr, idx_te = next(sss.split(X,y))
    sss2=StratifiedShuffleSplit(n_splits=1, test_size=0.1111, random_state=20250901)
    idx_tv, idx_va = next(sss2.split([X[i] for i in idx_tr],[y[i] for i in idx_tr]))
    val=[rows[i] for i in idx_va]
    return val
val=load_split()
texts=[r["text"] for r in val]; gold=[r["label"] for r in val]
X=hstack([B["char_vec"].transform(texts), B["word_vec"].transform(texts), rx(texts, B["regex_sources"])])
clf=B["clf"]; labels=clf.classes_.tolist()
marg=clf.decision_function(X)
P=softmax_margins(marg)
pred_idx=P.argmax(axis=1); pred=[labels[i] for i in pred_idx]; conf=P.max(axis=1)
cfg={}
if cfgp.exists():
    try: cfg=json.loads(cfgp.read_text(encoding="utf-8"))
    except Exception: cfg={}
target=0.85  # 你想要的 precision 門檻，可之後調
newcfg={}
for li,lab in enumerate(labels):
    cand=[c for p,c,g in zip(pred,conf,gold) if p==lab]
    good=[c for p,c,g in zip(pred,conf,gold) if p==lab and g==lab]
    if not cand:
        newcfg[lab]=cfg.get(lab,0.5); continue
    # 掃候選 conf，由高到低找 precision >= target 的最低門檻
    pairs=sorted([(c, (1 if g==lab else 0)) for p,c,g in zip(pred,conf,gold) if p==lab], reverse=True)
    tp=fp=0; best=cfg.get(lab,0.5)
    for c,is_tp in pairs:
        if is_tp: tp+=1
        else: fp+=1
        prec = tp/(tp+fp) if (tp+fp)>0 else 0
        if prec>=target:
            best=c;  # 當前 c 已滿足 precision
    newcfg[lab]=round(float(best),3)
cfgp.write_text(json.dumps(newcfg,ensure_ascii=False,indent=2),encoding="utf-8")
print("[TUNED]", newcfg)
