import json,os,pickle,re
from pathlib import Path
import numpy as np
from scipy.sparse import hstack,csr_matrix

ROOT=Path(".")
HOLD=ROOT/"data/intent/external_holdout.jsonl"
CFG =ROOT/".sma_tools/router_config.json"
MODEL="artifacts/intent_svm_plus_auto_cal.pkl"
if not Path(MODEL).exists(): MODEL="artifacts/intent_svm_plus_auto.pkl"

def featurize_regex(texts, rx_srcs):
    regs=[re.compile(p, re.I) for p in rx_srcs]
    return csr_matrix(np.array([[1 if rx.search(t) else 0 for rx in regs] for t in texts], dtype=np.float32))

rows=[json.loads(x) for x in HOLD.read_text(encoding="utf-8").splitlines() if x.strip()]
bundle=pickle.load(open(MODEL,"rb"))
texts=[r["text"] for r in rows]
X=hstack([bundle["char_vec"].transform(texts),
          bundle["word_vec"].transform(texts),
          featurize_regex(texts,bundle["regex_sources"])])
clf=bundle["clf"]; labels=clf.classes_.tolist()
marg=clf.decision_function(X)
if marg.ndim==1: marg=marg.reshape(-1,1)
# softmax-like 轉概率
e=np.exp(marg - marg.max(axis=1, keepdims=True)); probs=e/e.sum(axis=1, keepdims=True)
pred_idx=probs.argmax(axis=1)
pred=[labels[i] for i in pred_idx]
y=[r["label"] for r in rows]
pmax=probs.max(axis=1)

# 逐類別掃門檻，最大化 F1（自動 vs 人審）
cfg={}
for ci,lab in enumerate(labels):
    best_t=0.5; best_f1=-1.0
    y_bin=np.array([1 if yy==lab else 0 for yy in y])
    for t in np.linspace(0.30,0.80,26):
        auto=( (pred_idx==ci) & (pmax>=t) ).astype(int)
        TP=int(((auto==1) & (y_bin==1)).sum())
        FP=int(((auto==1) & (y_bin==0)).sum())
        FN=int(((auto==0) & (y_bin==1)).sum())
        prec=TP/(TP+FP) if (TP+FP)>0 else 0.0
        rec =TP/(TP+FN) if (TP+FN)>0 else 0.0
        f1 =2*prec*rec/(prec+rec) if (prec+rec)>0 else 0.0
        if f1>best_f1: best_f1=f1; best_t=float(t)
    cfg[lab]=round(best_t,2)
CFG.parent.mkdir(parents=True, exist_ok=True)
Path(CFG).write_text(json.dumps(cfg,ensure_ascii=False,indent=2), encoding="utf-8")
print("[TUNE] router_config.json", cfg)
