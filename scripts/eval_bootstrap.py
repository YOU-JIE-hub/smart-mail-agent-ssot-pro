import os, json, pathlib, time, random
from pathlib import Path
import numpy as np, joblib
from sklearn.metrics import accuracy_score, f1_score, classification_report

root=Path("."); out=(root/"reports_auto/pro/latest"); out.mkdir(parents=True, exist_ok=True)

def read_jsonl(p):
    p=Path(p)
    rows=[]
    if p.exists():
        for ln in p.read_text("utf-8").splitlines():
            ln=ln.strip()
            if ln:
                try: rows.append(json.loads(ln))
                except: pass
    return rows

def bootstrap_metrics(y_true, y_pred, B=1000, seed=42):
    rng=np.random.default_rng(seed)
    n=len(y_true); accs=[]; f1s=[]
    if n==0: return {"accuracy":{"mean":0,"ci95":[0,0]},"macro_f1":{"mean":0,"ci95":[0,0]}}
    y_true=np.array(y_true); y_pred=np.array(y_pred)
    for _ in range(B):
        idx=rng.integers(0,n,size=n)
        accs.append(accuracy_score(y_true[idx], y_pred[idx]))
        f1s.append(f1_score(y_true[idx], y_pred[idx], average="macro", zero_division=0))
    def ci(a): 
        a=sorted(a); lo=a[int(0.025*B)]; hi=a[int(0.975*B)]
        return float(np.mean(a)), [float(lo), float(hi)]
    mA, ciA = ci(accs); mF, ciF = ci(f1s)
    return {"accuracy":{"mean":mA,"ci95":ciA}, "macro_f1":{"mean":mF,"ci95":ciF}}

def eval_task(name, model_env, data_path, label_key="label"):
    pkl=os.environ.get(model_env,"")
    rows=read_jsonl(data_path)
    X=[r.get("text","") for r in rows]
    y=[r.get(label_key, 0) for r in rows]
    if name=="spam": y=[int(v) for v in y]
    res={"task":name, "n":len(X), "data_path":str(data_path), "model_env":model_env, "model_path":pkl}
    if not pkl or not Path(pkl).exists() or len(X)==0:
        res["status"]="skip"; return res
    m=joblib.load(pkl)
    y_pred=m.predict(X).tolist()
    res["status"]="ok"
    res["point"]={"accuracy": float(accuracy_score(y,y_pred)),
                  "macro_f1": float(f1_score(y,y_pred,average="macro",zero_division=0))}
    res["bootstrap"]=bootstrap_metrics(y,y_pred,B=1000,seed=42)
    return res

summ={}
summ["intent"]=eval_task("intent","INTENT_PKL", root/"data/intent_eval/test.jsonl", "label")
summ["spam"]=eval_task("spam","SPAM_PKL", root/"data/spam_eval/test.jsonl", "label")
(out/"bootstrap.json").write_text(json.dumps(summ, ensure_ascii=False, indent=2), "utf-8")
print("[OK] wrote", out/"bootstrap.json")
