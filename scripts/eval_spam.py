from __future__ import annotations
import argparse, json, pathlib
from typing import List, Dict, Any
from sklearn.metrics import classification_report, average_precision_score, roc_auc_score
from tools.config import get_model_paths
from tools.pipeline_baseline import load_model

def read_jsonl(p: pathlib.Path) -> list[dict]:
    out=[]
    if not p.exists(): return out
    with p.open("r", encoding="utf-8") as f:
        for ln in f: 
            ln=ln.strip()
            if ln: out.append(json.loads(ln))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", default=None)
    ap.add_argument("--data", default="data/spam_eval/dataset.cleaned.jsonl")
    ap.add_argument("--out",  default="reports_auto/spam/metrics.json")
    args = ap.parse_args()

    paths = get_model_paths(args.cfg)
    pipe, meta = load_model(paths.spam_pkl, "spam")
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    if meta.get("status")!="ok":
        with open(args.out, "w", encoding="utf-8") as f: json.dump({"spam": meta}, f, ensure_ascii=False, indent=2)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return

    data = read_jsonl(pathlib.Path(args.data))
    if not data:
        with open(args.out, "w", encoding="utf-8") as f: json.dump({"spam": {**meta, "warning":"no_eval_data"}}, f, ensure_ascii=False, indent=2)
        print("[WARN] no eval data"); return

    # 支援 text 或 subject+body
    X = [ d.get("text") or (d.get("subject","")+" "+d.get("body","")) for d in data ]
    y = [ int(d.get("y",0)) for d in data ]

    y_pred = pipe.predict(X)
    rep = classification_report(y, y_pred, output_dict=True, zero_division=0)

    try:
        y_score = pipe.predict_proba(X)[:,1]
        ap = float(average_precision_score(y, y_score))
        auc = float(roc_auc_score(y, y_score))
    except Exception:
        ap = auc = None

    out = {"spam": {"status":"ok","model_path":paths.spam_pkl,"n":len(X),"report":rep,"ap":ap,"auc":auc}}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__=="__main__":
    main()
