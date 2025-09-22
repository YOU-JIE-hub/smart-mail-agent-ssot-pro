import os, json, time, hashlib, glob, pathlib
from pathlib import Path
import numpy as np
import joblib
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, average_precision_score, precision_score, recall_score, f1_score

root = Path(".")
pro_root = root/"reports_auto"/"pro"; pro_root.mkdir(parents=True, exist_ok=True)
ts = time.strftime("%Y%m%dT%H%M%S")
outdir = pro_root/f"pro_{ts}"; outdir.mkdir(parents=True, exist_ok=True)

def py(o):
    try:
        import numpy as _np
        if isinstance(o, (_np.integer,)):  return int(o)
        if isinstance(o, (_np.floating,)): return float(o)
        if isinstance(o, (_np.ndarray,)):  return o.tolist()
    except Exception: pass
    if isinstance(o, set): return list(o)
    return o

def read_jsonl(p):
    p=Path(p)
    if not p.exists(): return []
    rows=[]
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        try: rows.append(json.loads(ln))
        except Exception: pass
    return rows

def write_tsv(path, rows, header=None):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with path.open("w", encoding="utf-8", newline="") as f:
        w=csv.writer(f, delimiter="\t")
        if header: w.writerow(header)
        for r in rows: w.writerow(r)

def model_prov(pkl_path):
    p=Path(pkl_path).expanduser().resolve()
    d={"path": str(p), "exists": p.exists()}
    if not p.exists(): return d
    b=p.read_bytes()
    d.update({"size_bytes": int(len(b)), "sha256": hashlib.sha256(b).hexdigest()})
    try:
        m=joblib.load(p)
        d["sklearn_pipeline"]=type(m).__name__
        d["classes_"]=list(getattr(m,"classes_",[]))
    except Exception as e:
        d["load_error"]=str(e)
    (p.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2, default=py), "utf-8")
    return d

summary={"created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

# ----- INTENT -----
intent={"task":"intent"}
idata_path=root/"data/intent_eval/test.jsonl"; intent["data_path"]=str(idata_path)
idata=read_jsonl(idata_path)
intent_path=os.environ.get("INTENT_PKL","")
if not intent_path:
    intent["status"]="missing_env"
else:
    try:
        m=joblib.load(intent_path)
        X=[r.get("text","") for r in idata]
        y=[r.get("label","") for r in idata]
        y_pred=m.predict(X).tolist() if X else []
        intent.update({"status":"ok","n":len(X),"model_path":intent_path})
        if X and y:
            cr=classification_report(y,y_pred,output_dict=True,zero_division=0)
            intent["metrics"]={"accuracy": float(cr.get("accuracy",0.0)),
                               "macro_f1": float(cr.get("macro avg",{}).get("f1-score",0.0))}
            labels=sorted(list({*y,*y_pred}))
            cm=confusion_matrix(y,y_pred,labels=labels).tolist()
            write_tsv(outdir/"intent_confusion_matrix.tsv", [[*labels]] + [[lbl,*row] for lbl,row in zip(labels, cm)])
            errs=[[i,t,p,txt[:200].replace("\t"," ")] for i,(t,p,txt) in enumerate(zip(y,y_pred,X)) if t!=p]
            write_tsv(outdir/"intent_errors_top.tsv", errs, header=["idx","true","pred","text"])
        else:
            intent["metrics"]={"accuracy":0.0,"macro_f1":0.0}
    except Exception as e:
        intent.update({"status":"error","error":str(e)})
summary["intent"]=intent

# ----- SPAM -----
spam={"task":"spam"}
sdata_path=root/"data/spam_eval/test.jsonl"; spam["data_path"]=str(sdata_path)
sdata=read_jsonl(sdata_path)
spam_path=os.environ.get("SPAM_PKL","")
if not spam_path:
    spam["status"]="missing_env"
else:
    try:
        m=joblib.load(spam_path)
        X=[r.get("text","") for r in sdata]
        y=[int(r.get("label",0)) for r in sdata]
        y_pred=m.predict(X).tolist() if X else []
        spam.update({"status":"ok","n":len(X),"model_path":spam_path})
        if X and y:
            cr=classification_report(y,y_pred,output_dict=True,zero_division=0)
            spam["metrics"]={"accuracy": float(cr.get("accuracy",0.0)),
                             "macro_f1": float(cr.get("macro avg",{}).get("f1-score",0.0))}
            if hasattr(m,"predict_proba"):
                try:
                    prob=m.predict_proba(X)[:,1]
                    if len(set(y))>1:
                        spam["roc_auc"]=float(roc_auc_score(y,prob))
                        spam["pr_auc"]=float(average_precision_score(y,prob))
                    bins=np.linspace(0.0,1.0,11)
                    idx=np.digitize(prob,bins)-1; y_np=np.array(y)
                    ece=0.0
                    for b in range(10):
                        mask=(idx==b)
                        if not np.any(mask): continue
                        conf=float(np.mean(prob[mask])); acc=float(np.mean((prob[mask]>=0.5)==y_np[mask])); w=float(np.mean(mask))
                        ece+=w*abs(acc-conf)
                    spam["ece"]=float(ece)
                    sweep=[]; best_f=-1.0; best_t=None; highp=None
                    for t in [round(x,2) for x in np.arange(0.10,0.91,0.05)]:
                        pred=(prob>=t).astype(int)
                        p=precision_score(y,pred,zero_division=0); r=recall_score(y,pred,zero_division=0); f=f1_score(y,pred,zero_division=0); a=float(np.mean(pred==y))
                        sweep.append([t,p,r,f,a])
                        if f>best_f: best_f, best_t=f, t
                        if highp is None and p>=0.98: highp=t
                    write_tsv(outdir/"spam_threshold_sweep.tsv", sweep, header=["threshold","precision","recall","f1","accuracy"])
                    spam["recommended_threshold"]={"rule":"precision>=0.98 pick min t else best f1","threshold": float(highp if highp is not None else best_t)}
                except Exception as e:
                    spam["proba_error"]=str(e)
            errs=[[i,t,p,txt[:200].replace("\t"," ")] for i,(t,p,txt) in enumerate(zip(y,y_pred,X)) if t!=p]
            write_tsv(outdir/"spam_errors_top.tsv", errs, header=["idx","true","pred","text"])
        else:
            spam["metrics"]={"accuracy":0.0,"macro_f1":0.0}
    except Exception as e:
        spam.update({"status":"error","error":str(e)})
summary["spam"]=spam

# ----- KIE -----
kie={"task":"kie","dir_env":"KIE_DIR","dir":os.environ.get("KIE_DIR","")}
try:
    req=["config.json","tokenizer.json","model.safetensors"]
    files, shapes={}, {}
    d=kie["dir"]
    if d:
        p=Path(d).expanduser().resolve()
        for n in req: files[n]=(p/n).exists()
        if files.get("model.safetensors"):
            try:
                from safetensors import safe_open
                with safe_open(str(p/"model.safetensors"), framework="pt") as f:
                    for k in list(f.keys())[:8]:
                        shapes[k]=list(f.get_tensor(k).shape)
            except Exception as e:
                shapes={"error":str(e)}
    kie["files"]=files; kie["sample_shapes"]=shapes; kie["status"]="ok"
except Exception as e:
    kie["status"]="error"; kie["error"]=str(e)
summary["kie"]=kie

# ----- Provenance -----
prov={}
if os.environ.get("INTENT_PKL"): prov["intent"]=model_prov(os.environ["INTENT_PKL"])
if os.environ.get("SPAM_PKL"):   prov["spam"]=model_prov(os.environ["SPAM_PKL"])
summary["provenance"]=prov

# 寫出 & latest
(outdir/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=py), "utf-8")
latest = pro_root/"latest"
try:
    if latest.exists() or latest.is_symlink(): latest.unlink()
    latest.symlink_to(outdir.relative_to(pro_root))
except Exception:
    (pro_root/"LATEST").write_text(str(outdir), "utf-8")
print("[OK] eval_pro done:", outdir)
