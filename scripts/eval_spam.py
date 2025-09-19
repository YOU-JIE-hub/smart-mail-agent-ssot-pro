import json, os, hashlib
from pathlib import Path
from sklearn.metrics import roc_auc_score, average_precision_score
import joblib
def load_dataset(paths):
    for p in paths:
        P=Path(p)
        if P.exists():
            ds=[]
            for line in P.read_text("utf-8",errors="ignore").splitlines():
                try:
                    obj=json.loads(line)
                    txt=obj.get("text") or obj.get("subject") or ""; y=obj.get("label") or obj.get("is_spam")
                    if y in (0,1,True,False): y=int(bool(y))
                    ds.append({"text":txt,"label":y})
                except: pass
            if ds: return ds
    return []
candidates=[
  "data/spam_eval/dataset.jsonl",
  "/home/youjie/projects/smart-mail-agent_ssot/data/spam_eval/dataset.jsonl"
]
ds=load_dataset(candidates)
out_dir=Path(f"models/spam/artifacts/v{os.environ.get('TODAY','')}")
out_dir.mkdir(parents=True, exist_ok=True)
met=out_dir/"metrics.json"; thr=out_dir/"thresholds.json"; card=out_dir/"MODEL_CARD.md"
res={"status":"skipped","reason":""}
try:
    mdlp=os.environ.get("SMA_SPAM_ML_PKL","/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/77/77/artifacts_sa/spam_rules_lr.pkl")
    if not Path(mdlp).exists(): res["reason"]="model_missing"
    elif not ds: res["reason"]="dataset_missing"
    else:
        clf=joblib.load(mdlp)
        X=[r["text"] for r in ds]; y=[r["label"] for r in ds]
        # 支援 decision_function / predict_proba
        try:
            s=clf.decision_function(X)
        except Exception:
            try:
                import numpy as np
                s=clf.predict_proba(X)[:,1]
            except Exception:
                # 退化：用預測 0/1 當分數
                import numpy as np
                s=clf.predict(X); s=s.astype(float)
        roc=roc_auc_score(y, s)
        pr=average_precision_score(y, s)
        # 簡單尋優 tau（Youden-like）；輸出 FPR@tau
        import numpy as np
        taus=np.linspace(0.05,0.95,19)
        best=(0,0.5,0,0) # (score,tau,prec,recall)
        from sklearn.metrics import precision_recall_fscore_support, confusion_matrix
        def fpr_at(y_true, score, tau):
            pred=(score>=tau).astype(int)
            tn, fp, fn, tp = confusion_matrix(y_true, pred).ravel()
            return fp/(fp+tn+1e-9)
        fprs={}
        for t in taus:
            pred=(s>=t).astype(int)
            from sklearn.metrics import precision_score, recall_score
            prec, rec = precision_score(y, pred, zero_division=0), recall_score(y, pred, zero_division=0)
            score=prec*rec
            fprs[round(float(t),2)]=float(fpr_at(y, s, t))
            if score>best[0]: best=(score,t,prec,rec)
        res={"status":"ok","roc_auc":float(roc),"pr_auc":float(pr),"fpr_at":fprs,"best_tau":best[1],"best_prec":best[2],"best_recall":best[3]}
        thr.write_text(json.dumps({"tau":best[1]}, indent=2), "utf-8")
    met.write_text(json.dumps(res,ensure_ascii=False,indent=2),"utf-8")
    if not card.exists(): card.write_text(f"# Model Card — spam (v{os.environ.get('TODAY','')})\n","utf-8")
    print("[spam.eval]",res["status"])
except Exception as e:
    met.write_text(json.dumps({"status":"error","error":str(e)},ensure_ascii=False,indent=2),"utf-8"); raise
