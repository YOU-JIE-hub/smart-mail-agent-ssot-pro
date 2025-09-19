import json, os, hashlib, sys
from pathlib import Path
from sklearn.metrics import f1_score, classification_report
import joblib
def safe_id(text):
    h=hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:12]; return f"sid_{h}"
def load_dataset(p):
    P=Path(p)
    if not P.exists(): return []
    ds=[]
    with P.open("r",encoding="utf-8",errors="ignore") as f:
        for line in f:
            try:
                obj=json.loads(line.strip()); 
                txt=obj.get("text") or obj.get("content") or obj.get("body") or ""
                y=obj.get("label") or obj.get("intent")
                _id=obj.get("id") or safe_id(txt)
                ds.append({"id":_id,"text":txt,"label":y})
            except: pass
    return ds
DATA="data/intent_eval/dataset.cleaned.jsonl"
ds=load_dataset(DATA)
out_dir=Path(f"models/intent/artifacts/v{os.environ.get('TODAY','')}")
out_dir.mkdir(parents=True, exist_ok=True)
met=out_dir/"metrics.json"; thr=out_dir/"thresholds.json"; card=out_dir/"MODEL_CARD.md"
res={"status":"skipped","reason":""}
try:
    mdlp=os.environ.get("SMA_INTENT_ML_PKL")
    if not mdlp or not Path(mdlp).exists(): 
        res["reason"]="model_missing"
    elif not ds:
        res["reason"]="dataset_missing"
    else:
        clf=joblib.load(mdlp)
        X=[r["text"] for r in ds]; y=[r["label"] for r in ds if r.get("label") is not None]
        if any(r.get("label") is None for r in ds):
            ds=[r for r in ds if r.get("label") is not None]; X=[r["text"] for r in ds]; y=[r["label"] for r in ds]
        y_pred=clf.predict(X)
        macro=f1_score(y, y_pred, average="macro")
        micro=f1_score(y, y_pred, average="micro")
        rep=classification_report(y, y_pred, output_dict=True, zero_division=0)
        res={"status":"ok","macro_f1":macro,"micro_f1":micro,"per_class":{k:v["f1-score"] for k,v in rep.items() if k not in ("accuracy","macro avg","weighted avg")}}
    met.write_text(json.dumps(res,ensure_ascii=False,indent=2),"utf-8")
    if not thr.exists(): thr.write_text(json.dumps({},indent=2), "utf-8")
    if not card.exists(): card.write_text(f"# Model Card — intent (v{os.environ.get('TODAY','')})\n", "utf-8")
    print("[intent.eval]",res["status"])
except Exception as e:
    met.write_text(json.dumps({"status":"error","error":str(e)},ensure_ascii=False,indent=2),"utf-8"); raise
