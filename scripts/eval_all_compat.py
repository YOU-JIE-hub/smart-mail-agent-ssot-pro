import os, json, time, hashlib
from pathlib import Path

def _to_jsonable(o):
    try:
        import numpy as np
        if isinstance(o, np.integer): return int(o)
        if isinstance(o, np.floating): return float(o)
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception:
        pass
    if isinstance(o, set): return list(o)
    return o

def _load_jsonl(p):
    p = Path(p)
    rows = []
    if not p.exists(): return [], "path_missing: {}".format(p)
    for line in p.read_text("utf-8").splitlines():
        line=line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except Exception as e: return [], "bad_jsonl: {} -> {}".format(p, e)
    return rows, None

def _provenance(pkl_path):
    pkl_path = Path(pkl_path)
    d={"path":str(pkl_path),"exists":pkl_path.exists(),"generated_at":time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not pkl_path.exists(): return d
    b=pkl_path.read_bytes()
    d["size_bytes"]=len(b)
    d["sha256"]=hashlib.sha256(b).hexdigest()
    try:
        import joblib, tools.compat_loader  # noqa
        m=joblib.load(pkl_path)
        d["classes_"]=list(getattr(m,"classes_",[]))
        d["sklearn_pipeline"]=type(m).__name__
    except Exception as e:
        d["load_error"]=str(e)
    (pkl_path.parent/"PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2, default=_to_jsonable),"utf-8")
    return d

def _eval_one(env_name, data_path):
    name_map={"INTENT_PKL":"intent","SPAM_PKL":"spam"}
    out={"task":name_map.get(env_name,env_name.lower()),"model_env":env_name,"data_path":str(data_path)}
    mp=os.environ.get(env_name)
    if not mp:
        out.update(status="error", error="{}_missing".format(env_name)); return out
    p=Path(mp).expanduser().resolve()
    out["model_path"]=str(p)
    if not p.exists():
        out.update(status="error", error="model_not_found: {}".format(p)); return out
    rows, err = _load_jsonl(data_path)
    if err:
        out.update(status="error", error=err); return out
    X=[r.get("text","") for r in rows]
    y=[r.get("label") for r in rows] if rows and "label" in rows[0] else None
    try:
        import joblib, tools.compat_loader  # noqa
        m=joblib.load(p)
        yp=m.predict(X)
    except Exception as e:
        out.update(status="error", error="predict_failed: {}".format(e), n=len(X)); return out
    out["status"]="ok"; out["n"]=len(X); out["classes_"]=list(getattr(m,"classes_",[]))
    if y is not None and all(v is not None for v in y):
        from sklearn.metrics import classification_report
        rep=classification_report(y, yp, zero_division=0, output_dict=True)
        out["metrics"]={"accuracy":float(rep.get("accuracy",0.0)),
                        "macro_f1":float(rep.get("macro avg",{}).get("f1-score",0.0))}
    else:
        out["sample_pred"]=[str(v) for v in yp[:10]]
    return out

def _check_kie():
    d=os.environ.get("KIE_DIR")
    out={"task":"kie","dir_env":"KIE_DIR","dir":d}
    if not d:
        out.update(status="error", error="KIE_DIR_missing"); return out
    p=Path(d).expanduser().resolve()
    need=["config.json","model.safetensors","tokenizer.json"]
    files={n:(p/n).exists() for n in need}
    out.update(status="ok" if all(files.values()) else "warn", files=files)
    return out

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--intent-data", default="data/intent_eval/test.jsonl")
    ap.add_argument("--spam-data",   default="data/spam_eval/test.jsonl")
    ap.add_argument("--out",         default="reports_auto/summary.json")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--print-classes", action="store_true")
    args=ap.parse_args()

    root=Path(".").resolve()
    (root/"reports_auto").mkdir(parents=True, exist_ok=True)

    if args.smoke:
        try:
            import joblib, tools.compat_loader  # noqa
            mi=joblib.load(Path(os.environ["INTENT_PKL"]).expanduser())
            ms=joblib.load(Path(os.environ["SPAM_PKL"]).expanduser())
            print("intent classes:", getattr(mi,"classes_",[]))
            print("intent pred   :", mi.predict(["想查一下合約報價與付款方式"])[0])
            print("spam classes  :", getattr(ms,"classes_",[]))
            print("spam pred     :", ms.predict(["FREE $$$ click here!!!"])[0])
        except Exception as e:
            print("[SMOKE ERROR]", e)
        return

    summ={"created_at":time.strftime("%Y-%m-%dT%H:%M:%S"),
          "intent":_eval_one("INTENT_PKL", args.intent_data),
          "spam":  _eval_one("SPAM_PKL",   args.spam_data),
          "kie":   _check_kie(),
          "provenance":{}}

    for k, env in (("intent","INTENT_PKL"), ("spam","SPAM_PKL")):
        p=os.environ.get(env)
        if p:
            summ["provenance"][k]=_provenance(Path(p).expanduser().resolve())

    Path(args.out).write_text(json.dumps(summ, ensure_ascii=False, indent=2, default=_to_jsonable), "utf-8")

    if args.print_classes:
        print("INTENT classes:", summ["intent"].get("classes_", []))
        print("SPAM   classes:", summ["spam"].get("classes_", []))

if __name__ == "__main__":
    main()
