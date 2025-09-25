#!/usr/bin/env python3
import os, sys, json, time, hashlib
from pathlib import Path
ROOT=Path(os.getcwd())
OUTDIR=ROOT/"reports_auto"/"pro"/time.strftime("%Y%m%dT%H%M%S")
OUTDIR.mkdir(parents=True, exist_ok=True)
LATEST=OUTDIR.parent/"latest"
def w(p,s): p.write_text(s,encoding="utf-8")
def import_app():
    from importlib import import_module
    for target in (os.getenv("APP","sma.api.app:app"),"sma.api.service_compat:app"):
        try: mod,attr=target.split(":",1); return getattr(import_module(mod),attr)
        except Exception: pass
    raise RuntimeError("ASGI import failed")
def client_of(app):
    try:
        from fastapi.testclient import TestClient
        return TestClient(app)
    except Exception:
        import httpx
        return httpx.Client(transport=httpx.ASGITransport(app=app), base_url="http://test")
def sha256_head(p:Path, n=16*1024*1024):
    h=hashlib.sha256()
    with p.open("rb") as f:
        if p.stat().st_size>n: h.update(f.read(n)); h.update(b"__TRUNC__")
        else:
            for c in iter(lambda:f.read(1<<20), b""): h.update(c)
    return h.hexdigest()
def file_stat(key):
    v=os.getenv(key,""); 
    if not v: return None
    p=Path(v); p=p if p.is_absolute() else ROOT/p
    if not p.exists(): return {"exists":False,"path":str(p)}
    d={"exists":True,"path":str(p.resolve())}
    if p.is_file(): d.update(kind="file",size=p.stat().st_size,sha256_head16mb=sha256_head(p))
    else: d.update(kind="dir")
    return d
def load_jsonl(p:Path):
    if not p or not p.exists(): return []
    out=[]
    for line in p.read_text(encoding="utf-8",errors="ignore").splitlines():
        line=line.strip()
        if not line: continue
        try: out.append(json.loads(line))
        except: pass
    return out
def std_label_spam(v):
    try:
        if isinstance(v,(int,float)): return "spam" if float(v)>=0.5 else "ham"
    except: pass
    return "spam" if str(v).strip().lower() in ("spam","1","true","yes") else "ham"
def macro_f1(y_true,y_pred,labels):
    def prf(tp,fp,fn):
        p=tp/(tp+fp) if (tp+fp)>0 else 0.0
        r=tp/(tp+fn) if (tp+fn)>0 else 0.0
        return 2*p*r/(p+r) if (p+r)>0 else 0.0
    f1s=[]
    for lab in labels:
        tp=sum(1 for a,b in zip(y_true,y_pred) if a==lab and b==lab)
        fp=sum(1 for a,b in zip(y_true,y_pred) if a!=lab and b==lab)
        fn=sum(1 for a,b in zip(y_true,y_pred) if a==lab and b!=lab)
        f1s.append(prf(tp,fp,fn))
    return sum(f1s)/len(f1s) if f1s else 0.0
def confusion_tsv(y_true,y_pred,labels,path:Path):
    labels=list(labels); rows=[]
    for t in labels:
        row=[t]+[str(sum(1 for a,b in zip(y_true,y_pred) if a==t and b==p)) for p in labels]
        rows.append("\t".join(row))
    w(path, "\t"+"\t".join(labels)+"\n"+"\n".join(rows)+"\n")
def choose_intent_labels():
    cfg=os.getenv("INTENT_CLASSES_JSON","")
    if cfg:
        p=Path(cfg); p=p if p.is_absolute() else ROOT/p
        if p.exists():
            try: return [str(x) for x in json.loads(p.read_text(encoding="utf-8"))]
            except: pass
    return None
APP=import_app(); CLIENT=client_of(APP)
def predict_intent(text):
    r=CLIENT.post("/v1/predict/intent", json={"text":text}, timeout=60)
    j=r.json() if hasattr(r,"json") else {}
    lab = j.get("label") or j.get("intent") or j.get("prediction") or "other"
    prob= j.get("proba") or j.get("probas") or j.get("probabilities")
    return str(lab), prob
def predict_spam(text):
    r=CLIENT.post("/v1/predict/spam", json={"text":text}, timeout=60)
    j=r.json() if hasattr(r,"json") else {}
    lab = std_label_spam(j.get("label"))
    score=None
    try:
        sc=j.get("score") or j.get("spam_score")
        score=float(sc) if sc is not None else None
    except: pass
    p_spam=None
    prob=j.get("proba") or j.get("probas") or j.get("probabilities")
    if isinstance(prob,dict):
        for k in ("spam","1","true"):
            if k in prob:
                try: p_spam=float(prob[k]); break
                except: pass
    if p_spam is None and score is not None: p_spam=max(0.0,min(1.0,float(score)))
    return lab, p_spam
def eval_task(name,data,label_std=None,labels_hint=None):
    y_true=[]; y_pred=[]; rec=[]
    for i,row in enumerate(data):
        text=row.get("text",""); truth=row.get("label","")
        if label_std: truth=label_std(truth)
        if name=="intent":
            pl,prob=predict_intent(text); y_true.append(str(truth)); y_pred.append(str(pl)); rec.append({"idx":i,"text":text,"true":truth,"pred":pl,"prob":prob})
        else:
            pl,p=predict_spam(text); y_true.append(str(truth)); y_pred.append(str(pl)); rec.append({"idx":i,"text":text,"true":truth,"pred":pl,"p_spam":p})
    labels=sorted(set(labels_hint or [] or set(y_true)|set(y_pred)))
    acc=sum(1 for a,b in zip(y_true,y_pred) if a==b)/len(y_true) if y_true else 0.0
    f1=macro_f1(y_true,y_pred,labels) if labels else 0.0
    return {"y_true":y_true,"y_pred":y_pred,"labels":labels,"acc":acc,"macro_f1":f1,"records":rec}
def write_errors_top(path, recs, limit=50):
    wrong=[r for r in recs if str(r["true"])!=str(r["pred"])]
    lines=["idx\ttrue\tpred\tp_spam\ttext"]
    for r in wrong[:limit]:
        lines.append(f"{r['idx']}\t{r['true']}\t{r['pred']}\t{(r.get('p_spam','') or '')}\t{r['text']}")
    w(path, "\n".join(lines)+"\n")
def threshold_sweep(path, recs):
    if not recs or any("p_spam" not in r or r["p_spam"] is None for r in recs):
        w(path,"threshold\tprecision\trecall\tf1\ttp\tfp\ttn\tfn\tsupport\n"); return None
    lines=["threshold\tprecision\trecall\tf1\ttp\tfp\ttn\tfn\tsupport"]; best=None
    for step in range(0,101):
        t=step/100.0; tp=fp=tn=fn=0
        for r in recs:
            pred="spam" if (r["p_spam"] or 0.0)>=t else "ham"; tru=std_label_spam(r["true"])
            if pred=="spam" and tru=="spam": tp+=1
            elif pred=="spam" and tru!="spam": fp+=1
            elif pred!="spam" and tru!="spam": tn+=1
            else: fn+=1
        p=tp/(tp+fp) if (tp+fp)>0 else 0.0; r=tp/(tp+fn) if (tp+fn)>0 else 0.0
        f1=2*p*r/(p+r) if (p+r)>0 else 0.0
        lines.append(f"{t:.2f}\t{p:.6f}\t{r:.6f}\t{f1:.6f}\t{tp}\t{fp}\t{tn}\t{fn}\t{tp+fn}")
        if p>=0.98 and best is None: best=t
    w(path,"\n".join(lines)+"\n"); return best
def main():
    intent_path=Path(os.getenv("INTENT_EVAL_JSONL","")); spam_path=Path(os.getenv("SPAM_EVAL_JSONL",""))
    intent_data=load_jsonl(intent_path) if str(intent_path) else []; spam_data=load_jsonl(spam_path) if str(spam_path) else []
    intent_labels_hint=choose_intent_labels()
    intent=eval_task("intent", intent_data, label_std=lambda x:str(x), labels_hint=intent_labels_hint)
    spam=eval_task("spam", spam_data, label_std=std_label_spam, labels_hint=["ham","spam"])
    confusion_tsv(intent["y_true"],intent["y_pred"],intent["labels"], OUTDIR/"confusion_matrix.tsv")
    write_errors_top(OUTDIR/"errors_top.tsv", spam["records"], 50)
    rec_t=threshold_sweep(OUTDIR/"threshold_sweep.tsv", spam["records"])
    prov={"intent_pkl":file_stat("INTENT_PKL"),"spam_pkl":file_stat("SPAM_PKL"),"kie_dir":file_stat("KIE_DIR"),"intent_classes_json":file_stat("INTENT_CLASSES_JSON"),"ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    summary={"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
             "metrics":{"intent":{"n":len(intent["y_true"]),"labels":intent["labels"],"accuracy":round(intent["acc"],6),"macro_f1":round(intent["macro_f1"],6)},
                        "spam":{"n":len(spam["y_true"]),"labels":["ham","spam"],"accuracy":round(sum(1 for a,b in zip(spam["y_true"],spam["y_pred"]) if a==b)/len(spam["y_true"]) if spam["y_true"] else 0.0,6),"macro_f1":round(macro_f1(spam["y_true"],spam["y_pred"],["ham","spam"]),6),"recommended_threshold_precision>=0.98": (None if rec_t is None else round(float(rec_t),2))}},
             "provenance": prov}
    w(OUTDIR/"summary.json", json.dumps(summary,ensure_ascii=False,indent=2))
    try:
        if LATEST.exists() or LATEST.is_symlink(): LATEST.unlink()
        LATEST.symlink_to(OUTDIR)
    except Exception: pass
    print(str(OUTDIR))
if __name__=="__main__": main()
