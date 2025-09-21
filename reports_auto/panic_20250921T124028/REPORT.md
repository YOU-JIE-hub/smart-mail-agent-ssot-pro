# Panic Report
- Exit code: 1
- CMD  : . .venv/bin/activate; python3 - <<'PY'
from pathlib import Path
import textwrap

root = Path(".")
(root/"scripts").mkdir(exist_ok=True)

# --- eval_all_compat.py（單檔總評 CLI，讀三個 ENV、輸出 summary.json）
eval_code = r"""
import os, sys, json, time, hashlib
from pathlib import Path

def _to_jsonable(o):
    try:
        import numpy as np
        if isinstance(o, np.integer): return int(o)
        if isinstance(o, np.floating): return float(o)
        if isinstance(o, np.ndarray): return o.tolist()
    except Exception: pass
    if isinstance(o, set): return list(o)
    return o

def _load_jsonl(p):
    p = Path(p)
    rows = []
    if not p.exists(): return [], "path_missing: {}".format(p)
    for line in p.read_text("utf-8").splitlines():
        line=line.strip()
        if line:
            try: rows.append(json.loads(line))
            except Exception as e: return [], "bad_jsonl: {} -> {}".format(p, e)
    return rows, None

def _provenance(pkl_path):
    d = {"path": str(pkl_path), "exists": pkl_path.exists(), "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not pkl_path.exists(): return d
    b = pkl_path.read_bytes()
    d["size_bytes"] = len(b)
    d["sha256"] = hashlib.sha256(b).hexdigest()
    try:
        import joblib, tools.compat_loader  # noqa
        m = joblib.load(pkl_path)
        d["classes_"] = list(getattr(m, "classes_", []))
        d["sklearn_pipeline"] = type(m).__name__
    except Exception as e:
        d["load_error"] = str(e)
    (pkl_path.parent / "PROVENANCE.json").write_text(json.dumps(d, ensure_ascii=False, indent=2, default=_to_jsonable), "utf-8")
    return d

def _eval_one(env_name, data_path):
    out = {"task": env_name.lower(), "model_env": env_name, "data_path": str(data_path)}
    mp = os.environ.get(env_name)
    if not mp: out.update(status="error", error="{}_missing".format(env_name)); return out
    p = Path(mp).expanduser().resolve()
    out["model_path"] = str(p)
    if not p.exists(): out.update(status="error", error="model_not_found: {}".format(p)); return out
    rows, err = _load_jsonl(data_path)
    if err: out.update(status="error", error=err); return out
    X = [r.get("text","") for r in rows]
    y = [r.get("label") for r in rows] if rows and "label" in rows[0] else None
    try:
        import joblib, tools.compat_loader  # noqa
        m = joblib.load(p)
        yp = m.predict(X)
    except Exception as e:
        out.update(status="error", error="predict_failed: {}".format(e), n=len(X)); return out
    out["status"] = "ok"; out["n"] = len(X); out["classes_"] = list(getattr(m,"classes_",[]))
    if y is not None and all(v is not None for v in y):
        from sklearn.metrics import classification_report
        rep = classification_report(y, yp, zero_division=0, output_dict=True)
        out["metrics"] = {"accuracy": float(rep.get("accuracy",0.0)),
                          "macro_f1": float(rep.get("macro avg",{}).get("f1-score",0.0))}
    else:
        out["sample_pred"] = [str(v) for v in yp[:10]]
    return out

def _check_kie():
    d = os.environ.get("KIE_DIR")
    out = {"task":"kie","dir_env":"KIE_DIR","dir":d}
    if not d: out.update(status="error", error="KIE_DIR_missing"); return out
    p = Path(d).expanduser().resolve()
    need = ["config.json","model.safetensors","tokenizer.json"]
    files = {n: (p/n).exists() for n in need}
    out.update(status="ok" if all(files.values()) else "warn", files=files)
    return out

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--intent-data", default="data/intent_eval/test.jsonl")
    ap.add_argument("--spam-data",   default="data/spam_eval/test.jsonl")
    ap.add_argument("--out",         default="reports_auto/summary.json")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--print-classes", action="store_true")
    a = ap.parse_args()

    root = Path(".").resolve()
    (root/"reports_auto").mkdir(parents=True, exist_ok=True)

    if a.smoke:
        try:
            import joblib, tools.compat_loader  # noqa
            mi = joblib.load(Path(os.environ["INTENT_PKL"]).expanduser())
            ms = joblib.load(Path(os.environ["SPAM_PKL"]).expanduser())
            print("intent classes:", getattr(mi,"classes_",[])); print("intent pred   :", mi.predict(["想查一下合約報價與付款方式"])[0])
            print("spam classes  :", getattr(ms,"classes_",[])); print("spam pred     :", ms.predict(["FREE $$$ click here!!!"])[0])
        except Exception as e:
            print("[SMOKE ERROR]", e)
        return

    summ = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "intent": _eval_one("INTENT_PKL", a.intent_data),
        "spam":   _eval_one("SPAM_PKL",   a.spam_data),
        "kie":    _check_kie(),
        "provenance": {}
    }
    for k, env in (("intent","INTENT_PKL"), ("spam","SPAM_PKL")):
        p = os.environ.get(env)
        if p: summ["provenance"][k] = _provenance(Path(p).expanduser().resolve())
    Path(a.out).write_text(json.dumps(summ, ensure_ascii=False, indent=2, default=_to_jsonable), "utf-8")
    if a.print_classes:
        print("INTENT classes:", summ["intent"].get("classes_", []))
        print("SPAM   classes:", summ["spam"].get("classes_", []))

if __name__ == "__main__":
    main()
"""
(root/"scripts/eval_all_compat.py").write_text(eval_code, encoding="utf-8")

# --- build_summary_md.py（由 summary.json 產出 summary.md）
md_code = r"""
import json, pathlib
root=pathlib.Path(".")
j=json.loads((root/"reports_auto/summary.json").read_text("utf-8"))
lines=[]
lines.append("# Smart Mail Agent — 煙霧測試摘要（" + str(j.get("created_at","")) + "）\n")
def sec(name):
    m=j.get(name,{})
    lines.append("## " + name.upper() + "\n")
    if m.get("status")!="ok":
        lines.append("- 狀態：" + str(m.get("status")) + "  \n- 錯誤：" + str(m.get("error")) + "\n"); return
    if name!="kie":
        lines.append("- 範例數：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n- classes：" + json.dumps(m.get("classes_",[]), ensure_ascii=False) + "\n")
        met=m.get("metrics",{})
        if met:
            lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
    else:
        files=m.get("files",{})
        lines.append("- 目錄：`" + str(m.get("dir","")) + "`  \n- 狀態：" + str(m.get("status")) + "  \n- 必要檔：" + json.dumps(files, ensure_ascii=False) + "\n")
for k in ("intent","spam","kie"): sec(k)
out=(root/"reports_auto/eval"); out.mkdir(parents=True, exist_ok=True)
(out/"summary.md").write_text("".join(lines), encoding="utf-8")
print("[OK] wrote", out/"summary.md")
"""
(root/"scripts/build_summary_md.py").write_text(md_code, encoding="utf-8")

# --- Makefile.compat（把規則放到獨立檔，主 Makefile 只 include）
frag = "\n".join([
".PHONY: eval-compat summary-md smoke",
"",
"eval-compat:",
"\t@bash tools/panic.sh . .venv/bin/activate
- LOG  : reports_auto/panic_20250921T124028/run.log
- ERR  : reports_auto/panic_20250921T124028/run.err
- PY   : reports_auto/panic_20250921T124028/python_stderr.txt
- OOM  : reports_auto/panic_20250921T124028/oom.txt
- TRACE: reports_auto/panic_20250921T124028/xtrace.sh
- SYS  : reports_auto/panic_20250921T124028/system.txt

## Heuristics
