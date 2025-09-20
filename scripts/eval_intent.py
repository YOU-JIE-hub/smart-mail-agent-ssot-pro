from __future__ import annotations
import argparse, json, pathlib, sys
from typing import List, Dict, Any
from sklearn.metrics import classification_report
from tools.config import get_model_paths
from tools.pipeline_baseline import load_model
from vendor.rules_features import feature_schema_from_fitted

def read_jsonl(p: pathlib.Path) -> List[Dict[str, Any]]:
    out=[]
    if not p.exists(): return out
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            out.append(json.loads(line))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", default=None)
    ap.add_argument("--data", default="data/intent_eval/dataset.cleaned.jsonl")
    ap.add_argument("--out",  default="reports_auto/intent/metrics.json")
    args = ap.parse_args()

    paths = get_model_paths(args.cfg)
    pipe, meta = load_model(paths.intent_pkl, "intent")
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    if meta.get("status")!="ok":
        meta["status"]="error"
        with open(args.out, "w", encoding="utf-8") as f: json.dump({"intent": meta}, f, ensure_ascii=False, indent=2)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        sys.exit(1)

    data = read_jsonl(pathlib.Path(args.data))
    if not data:
        with open(args.out, "w", encoding="utf-8") as f: json.dump({"intent": {**meta, "warning":"no_eval_data"}}, f, ensure_ascii=False, indent=2)
        print("[WARN] no eval data"); return

    X = [d.get("text","") for d in data]
    y = [d.get("label","") for d in data]

    y_pred = pipe.predict(X)
    rep = classification_report(y, y_pred, output_dict=True, zero_division=0)

    # features schema（若已 fit）
    try:
        feat_schema = feature_schema_from_fitted(dict(pipe.steps)["features"])
    except Exception:
        feat_schema = None

    out = {
        "intent":{
            "status":"ok",
            "model_path": paths.intent_pkl,
            "n": len(X),
            "report": rep,
            "feature_schema": feat_schema,
        }
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__=="__main__":
    main()
