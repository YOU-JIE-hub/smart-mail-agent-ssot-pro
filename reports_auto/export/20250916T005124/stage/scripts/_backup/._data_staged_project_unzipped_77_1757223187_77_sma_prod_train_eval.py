#!/usr/bin/env python3
from __future__ import annotations
import json, numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
from _sma_rules import spam_signals_text

def load(fp):
    X,y,rows=[],[],[]
    for line in Path(fp).read_text(encoding="utf-8").splitlines():
        e=json.loads(line); rows.append(e)
        X.append((e.get("subject","")+" \n "+e.get("body","")))
        y.append(1 if e["label"]=="spam" else 0)
    return X, np.array(y), rows

def prf(y, yhat):
    P,R,F1,_=precision_recall_fscore_support(y,yhat,average=None,labels=[0,1])
    cm=confusion_matrix(y,yhat,labels=[0,1]).tolist()
    macro=(F1[0]+F1[1])/2
    return macro,P,R,F1,cm

def write_eval(tag, macro,P,R,F1,cm, out):
    out.write_text(
        (f"[SPAM][EVAL] macro_f1={macro:.4f}\n"
         f"[SPAM][EVAL] ham  P/R/F1 = {P[0]:.3f}/{R[0]:.3f}/{F1[0]:.3f}\n"
         f"[SPAM][EVAL] spam P/R/F1 = {P[1]:.3f}/{R[1]:.3f}/{F1[1]:.3f}\n"
         f"[SPAM][EVAL] confusion = {cm}\n")
    )

DATA = Path("data/prod_merged")
Xtr,ytr,_=load(DATA/"train.jsonl")
Xva,yva, rva = load(DATA/"val.jsonl")
Xte,yte, rte = load(DATA/"test.jsonl")

# ---- 訓練：向量化 -> LR -> Platt 校準(在 Val) ----
vect=TfidfVectorizer(analyzer="char", ngram_range=(3,5), min_df=2, max_df=0.95, sublinear_tf=True)
Xtrv=vect.fit_transform(Xtr)
base=LogisticRegression(max_iter=200, solver="liblinear")
base.fit(Xtrv, ytr)
cal=CalibratedClassifierCV(base, method="sigmoid", cv="prefit")
cal.fit(vect.transform(Xva), yva)
pipe=Pipeline([("vect", vect), ("cal", cal)])

# 保存成 Pipeline（避免日後再組裝）
Path("artifacts_prod").mkdir(parents=True, exist_ok=True)
import joblib; joblib.dump(pipe, "artifacts_prod/text_lr_platt.pkl")

# ---- Val 上掃描門檻 -> 先滿足 spamR>=0.95，再取 Macro-F1 最大 ----
pva=pipe.predict_proba(Xva)[:,1]
best={"thr":0.5,"macro":-1,"spamR":-1}
ts=[round(x,2) for x in np.linspace(0.10,0.60,51)]
with open("reports_auto/prod_sweep.tsv","w",encoding="utf-8") as w:
    w.write("thr\tmacroF1\thamP\thamR\thamF1\tspamP\tspamR\tspamF1\n")
    for t in ts:
        yhat=(pva>=t).astype(int)
        macro,P,R,F1,_=prf(yva,yhat)
        w.write(f"{t}\t{macro:.4f}\t{P[0]:.3f}\t{R[0]:.3f}\t{F1[0]:.3f}\t{P[1]:.3f}\t{R[1]:.3f}\t{F1[1]:.3f}\n")
        # 先看 spamR，>=0.95 中挑 macroF1 最大；若無，取 spamR 最大
        if R[1]>=0.95 and macro>best["macro"]:
            best={"thr":t,"macro":macro,"spamR":R[1]}
if best["macro"]<0:  # 沒有達到 0.95，就取 spamR 最大（再看 macro）
    rows=[l.strip().split("\t") for l in Path("reports_auto/prod_sweep.tsv").read_text().splitlines()[1:]]
    rows=[{"thr":float(r[0]),"macro":float(r[1]),"spamR":float(r[6])} for r in rows]
    rows.sort(key=lambda x:(x["spamR"],x["macro"]), reverse=True)
    best=rows[0]

# ---- 固化門檻與規則信號下限（2/3/4 掃描，選 spamR 優先）----
def rule_scan(rows, k):
    y=np.array([1 if e["label"]=="spam" else 0 for e in rows])
    yhat=np.array([1 if spam_signals_text(e.get("subject",""), e.get("body",""), e.get("attachments"))>=k else 0 for e in rows])
    macro,P,R,F1,_=prf(y,yhat)
    return {"k":k,"macro":macro,"spamR":R[1]}
cands=[rule_scan(rva,k) for k in (2,3,4)]
cands.sort(key=lambda x:(x["spamR"],x["macro"]), reverse=True)
signals_min=cands[0]["k"]

Path("artifacts_prod/ens_thresholds.json").write_text(json.dumps({
    "threshold": best["thr"], "signals_min": int(signals_min)
}, ensure_ascii=False))

# ---- 在 Test 上評估：Text / Rule / Ensemble ----
pte=pipe.predict_proba(Xte)[:,1]; thr=best["thr"]
yt=np.array([1 if p>=thr else 0 for p in pte])
yr=np.array([1 if spam_signals_text(e.get("subject",""), e.get("body",""), e.get("attachments"))>=signals_min else 0 for e in rte])
ye=np.maximum(yt, yr)

macro,P,R,F1,cm=prf(np.array([1 if e["label"]=="spam" else 0 for e in rte]), yt)
write_eval("TEXT", macro,P,R,F1,cm, Path("reports_auto/prod_eval_text_only.txt"))
macro,P,R,F1,cm=prf(np.array([1 if e["label"]=="spam" else 0 for e in rte]), yr)
write_eval("RULE", macro,P,R,F1,cm, Path("reports_auto/prod_eval_rule_only.txt"))
macro,P,R,F1,cm=prf(np.array([1 if e["label"]=="spam" else 0 for e in rte]), ye)
write_eval("ENS",  macro,P,R,F1,cm, Path("reports_auto/prod_eval_ensemble.txt"))

print(f"[OK] model -> artifacts_prod/text_lr_platt.pkl")
print(f"[OK] thr   -> artifacts_prod/ens_thresholds.json")
print(f"[OK] evals -> reports_auto/prod_eval_*.txt ; sweep -> reports_auto/prod_sweep.tsv")
