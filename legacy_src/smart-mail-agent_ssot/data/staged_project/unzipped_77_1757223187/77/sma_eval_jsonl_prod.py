#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import numpy as np, joblib
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

RE_URL=re.compile(r"https?://[^\s)>\]]+",re.I)
SUS_TLD={".zip",".xyz",".top",".cam",".shop",".work",".loan",".country",".gq",".tk",".ml",".cf"}
SUS_EXT={".zip",".rar",".7z",".exe",".js",".vbs",".bat",".cmd",".htm",".html",".lnk",".iso",".docm",".xlsm",".pptm",".scr"}
KW=["重設密碼","驗證","帳戶異常","登入異常","補件","逾期","海關","匯款","退款","發票","稅務","罰款",
    "verify","reset","2fa","account","security","login","signin","update","confirm","invoice","payment","urgent","limited","verify your account"]

def spam_signals(e):
    subj=(e.get("subject","") or ""); body=(e.get("body","") or "")
    t=(subj+" "+body).lower()
    urls=RE_URL.findall(t); atts=[(a or "").lower() for a in e.get("attachments",[]) if a]
    sig=0
    if urls: sig+=1
    if any(u.lower().endswith(t) for u in urls for t in SUS_TLD): sig+=1
    if any(k in t for k in KW): sig+=1
    if any(a.endswith(ext) for a in atts for ext in SUS_EXT): sig+=1
    if ("account" in t) and (("verify" in t) or ("reset" in t) or ("login" in t) or ("signin" in t)): sig+=1
    if ("帳戶" in t) and (("驗證" in t) or ("重設" in t) or ("登入" in t)): sig+=1
    return sig

def load_jsonl(fp:Path):
    rows=[]
    with open(fp,encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    X=[(r.get("subject","")+" \n "+r.get("body","")) for r in rows]
    y=np.array([1 if r.get("label")=="spam" else 0 for r in rows])
    return rows, X, y

def metrics(y, yhat):
    P,R,F,_=precision_recall_fscore_support(y,yhat,labels=[0,1],zero_division=0)
    cm=confusion_matrix(y,yhat,labels=[0,1])
    macro=(F[0]+F[1])/2
    return macro, (P[0],R[0],F[0]), (P[1],R[1],F[1]), cm

ap=argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--mode", choices=["rule","text","ensemble"], default="ensemble")
ap.add_argument("--model", default="artifacts_prod/text_lr_platt.pkl")
ap.add_argument("--thr", type=float, default=None)
ap.add_argument("--signals_min", type=int, default=None)
ap.add_argument("--out", default="")
a=ap.parse_args()

thr_file=json.load(open("artifacts_prod/ens_thresholds.json"))
thr=a.thr if a.thr is not None else float(thr_file["threshold"])
sig_min=a.signals_min if a.signals_min is not None else int(thr_file["signals_min"])
rows,X,y=load_jsonl(Path(a.data))
clf=joblib.load(a.model)

probs=clf.predict_proba(X)[:,1]
rule=np.array([1 if spam_signals(r)>=sig_min else 0 for r in rows])
text=(probs>=thr).astype(int)
pred = rule if a.mode=="rule" else text if a.mode=="text" else np.where((rule==1)|(text==1),1,0)

macro,ham,spam,cm=metrics(y,pred)
print(f"[SPAM][EVAL] macro_f1={macro:.4f} thr={thr:.2f} signals_min={sig_min} mode={a.mode}")
print(f"[SPAM][EVAL] ham  P/R/F1 = {ham[0]:.3f}/{ham[1]:.3f}/{ham[2]:.3f}")
print(f"[SPAM][EVAL] spam P/R/F1 = {spam[0]:.3f}/{spam[1]:.3f}/{spam[2]:.3f}")
print(f"[SPAM][EVAL] confusion = {cm.tolist()}")
if a.out:
    with open(a.out,"w",encoding="utf-8") as w: w.write("\n".join([
        f"[SPAM][EVAL] macro_f1={macro:.4f} thr={thr:.2f} signals_min={sig_min} mode={a.mode}",
        f"[SPAM][EVAL] ham  P/R/F1 = {ham[0]:.3f}/{ham[1]:.3f}/{ham[2]:.3f}",
        f"[SPAM][EVAL] spam P/R/F1 = {spam[0]:.3f}/{spam[1]:.3f}/{spam[2]:.3f}",
        f"[SPAM][EVAL] confusion = {cm.tolist()}",
    ]))
