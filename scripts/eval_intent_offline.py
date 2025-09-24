#!/usr/bin/env python
import os, sys, json, argparse, datetime, pathlib
from typing import List, Dict, Any
from sma.common.intent_compat import load_pipeline, predict_proba_batch, meta as intent_meta
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
import numpy as np

def read_jsonl(path): 
    out=[]; 
    with open(path, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f,1):
            line=line.strip(); 
            if not line: continue
            try: out.append(json.loads(line))
            except Exception as e: 
                print(f"[ERR] JSONL parse error at line {ln}: {e}", file=sys.stderr); sys.exit(3)
    return out

def compute_ece_maxconf(y_true, proba, n_bins=15):
    y_true=np.array(y_true); pred=proba.argmax(axis=1); conf=proba.max(axis=1); correct=(pred==y_true).astype(float)
    bins=np.linspace(0.0,1.0,n_bins+1); ece=0.0; stats=[]
    for i in range(n_bins):
        m=(conf>=bins[i]) & (conf<(bins[i+1]) if i<n_bins-1 else conf<=bins[i+1])
        if not m.any(): stats.append({"bin":i,"count":0,"conf":None,"acc":None}); continue
        acc=correct[m].mean(); c=conf[m].mean(); w=m.mean(); ece+=w*abs(acc-c); stats.append({"bin":i,"count":int(m.sum()),"conf":float(c),"acc":float(acc)})
    return float(ece), stats

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--text-field", required=True)
    ap.add_argument("--label-field", required=True)
    ap.add_argument("--output-dir")
    args=ap.parse_args()

    data=read_jsonl(args.data)
    if not data: print("[FATAL] 資料為空", file=sys.stderr); sys.exit(2)

    keys=set().union(*[d.keys() for d in data])
    missing=[k for k in (args.text_field,args.label_field) if k not in keys]
    if missing:
        print(f"[FATAL] 找不到欄位：{missing}；可用鍵：{sorted(keys)}", file=sys.stderr); sys.exit(2)

    X=[d[args.text_field] for d in data]
    y_names=[d[args.label_field] for d in data]

    pkl=os.getenv("INTENT_PKL"); 
    if not pkl or not pathlib.Path(pkl).exists(): 
        print(f"[FATAL] 缺少 INTENT_PKL（{pkl}）", file=sys.stderr); sys.exit(2)
    load_pipeline(pkl)
    proba, classes = predict_proba_batch(X)
    if not classes: classes = intent_meta().get("classes_", [])

    name2id={n:i for i,n in enumerate(classes)}
    unknown=sorted(set(y_names)-set(classes))
    if unknown:
        print(f"[FATAL] 驗證資料存在未知標籤：{unknown}；模型 classes_={classes}", file=sys.stderr); sys.exit(2)

    y_true=np.array([name2id[n] for n in y_names], dtype=int); y_pred=proba.argmax(axis=1)

    acc=accuracy_score(y_true,y_pred); f1_m=f1_score(y_true,y_pred,average="macro")
    f1_w=f1_score(y_true,y_pred,average="weighted"); f1_u=f1_score(y_true,y_pred,average="micro")
    cm=confusion_matrix(y_true,y_pred,labels=list(range(len(classes))))
    rep=classification_report(y_true,y_pred,target_names=classes,digits=4)
    ece,bins=compute_ece_maxconf(y_true,proba,n_bins=15)

    ts=datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    outdir=args.output_dir or f"reports_auto/pro/intent_eval_{ts}"
    pathlib.Path(outdir).mkdir(parents=True, exist_ok=True)

    json.dump({"ts":ts,"data":args.data,"count":len(X),"classes":classes,
               "metrics":{"accuracy":acc,"f1_macro":f1_m,"f1_weighted":f1_w,"f1_micro":f1_u,"ece_maxconf":ece}},
              open(f"{outdir}/summary.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    open(f"{outdir}/classification_report.txt","w",encoding="utf-8").write(rep)
    with open(f"{outdir}/confusion_matrix.csv","w",encoding="utf-8") as f:
        f.write(",".join([""]+classes)+"\n")
        for i,row in enumerate(cm): f.write(",".join([classes[i]]+[str(int(x)) for x in row])+"\n")
    json.dump(bins, open(f"{outdir}/reliability_bins.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    with open(f"{outdir}/pred_details.tsv","w",encoding="utf-8") as f:
        f.write("text\ttrue\tpred\tconf\n")
        for t,yt,yp,pv in zip(X,y_true,y_pred,proba.max(axis=1)):
            f.write(f"{str(t).replace(chr(9),' ')}\t{classes[int(yt)]}\t{classes[int(yp)]}\t{float(pv):.6f}\n")
    md = ["# Intent Offline Eval", f"- data: `{args.data}`", f"- n: {len(X)}", f"- classes: {classes}",
          "## Metrics", f"- accuracy: **{acc:.4f}**", f"- F1 (macro): **{f1_m:.4f}**",
          f"- F1 (micro): **{f1_u:.4f}**", f"- F1 (weighted): **{f1_w:.4f}**", f"- ECE (max-conf): **{ece:.4f}**",
          "## Classification report", "```", rep, "```"]
    open(f"{outdir}/summary.md","w",encoding="utf-8").write("\n".join(md))
    print(f"[OK] intent eval -> {outdir}")
    print("  - summary.json / summary.md")
    print("  - classification_report.txt / confusion_matrix.csv")
    print("  - reliability_bins.json / pred_details.tsv")
if __name__ == "__main__": main()
