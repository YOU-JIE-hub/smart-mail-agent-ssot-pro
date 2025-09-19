from __future__ import annotations
import os, sys, json, collections, joblib
from sklearn.metrics import classification_report, confusion_matrix
TO_ZH={"biz_quote":"報價","tech_support":"技術支援","complaint":"投訴","policy_qa":"規則詢問","profile_update":"資料異動","other":"其他"}
ZH2EN={v:k for k,v in TO_ZH.items()}

def load_dataset(p):
    xs,ys=[],[]
    with open(p,"r",encoding="utf-8") as f:
        for l in f:
            if not l.strip(): continue
            d=json.loads(l)
            xs.append(d.get("text") or d.get("content") or d.get("utterance") or "")
            ys.append(str(d.get("label") or d.get("intent") or ""))
    return xs,ys

def main():
    pkl=os.environ.get("SMA_INTENT_ML_PKL","").strip()
    ds =os.environ.get("SMA_INTENT_EVAL_DS","data/intent_eval/dataset.cleaned.jsonl").strip()
    if not os.path.exists(pkl): print("[FATAL] model not found:",pkl); sys.exit(2)
    if not os.path.exists(ds):  print("[FATAL] dataset not found:",ds); sys.exit(2)
    obj=joblib.load(pkl); pipe=obj.get("pipe") if isinstance(obj,dict) else obj
    xs,gold_zh=load_dataset(ds)
    pred_en=pipe.predict(xs); pred_zh=[TO_ZH.get(str(y),str(y)) for y in pred_en]
    mask=[g in ZH2EN for g in gold_zh]
    g=[ZH2EN[g] for g,m in zip(gold_zh,mask) if m]
    p=[y for y,m in zip(pred_en,mask) if m]
    print("classes(model):", getattr(pipe,"classes_",None))
    print("n(samples):", len(xs), "  n(evalable):", len(g))
    print("\n== classification_report ==")
    print(classification_report(g,p,labels=getattr(pipe,"classes_",None)))
    print("== confusion_matrix ==")
    print(confusion_matrix(g,p,labels=getattr(pipe,"classes_",None)))
