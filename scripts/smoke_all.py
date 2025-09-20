import os, sys, json, traceback
from pathlib import Path
from datetime import datetime
import joblib

ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / f"reports_auto/smoke_all_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
OUTD.mkdir(parents=True, exist_ok=True)

def load_any(pkl_path: str):
    # old-pickle shim
    try:
        from vendor import rules_features as RF
        import builtins
        sys.modules.setdefault("__main__", builtins)
        setattr(sys.modules["__main__"], "rules_feat", getattr(RF, "rules_feat", lambda x: {}))
        setattr(sys.modules["__main__"], "rules_feat_func", getattr(RF, "rules_feat_func", getattr(RF, "rules_feat", lambda x: {})))
    except Exception:
        import builtins
        sys.modules.setdefault("__main__", builtins)
        setattr(sys.modules["__main__"], "rules_feat", lambda x: {})
        setattr(sys.modules["__main__"], "rules_feat_func", lambda x: {})

    obj = joblib.load(pkl_path)
    pipe = obj
    if isinstance(obj, dict):
        for k in ("pipeline","model","clf"):
            if k in obj: pipe = obj[k]; break
    return pipe

def probe(pipe):
    info = {"steps": None, "classes": None, "vocab_size": None}
    if hasattr(pipe, "steps"):
        info["steps"] = [n for n,_ in pipe.steps]
        for n,st in pipe.named_steps.items():
            if hasattr(st, "vocabulary_"):
                info["vocab_size"] = len(st.vocabulary_)
                break
        # classifier classes
        for n,st in reversed(pipe.steps):
            stobj = pipe.named_steps[n]
            if hasattr(stobj, "classes_"):
                info["classes"] = [str(c) for c in stobj.classes_]
                break
    elif hasattr(pipe, "classes_"):
        info["classes"] = [str(c) for c in pipe.classes_]
    return info

def predict_safe(pipe, texts):
    try:
        return list(map(str, pipe.predict(texts)))
    except Exception as e:
        return f"predict_failed: {e}"

intent_p = os.environ.get("INTENT_PKL") or "models/intent/artifacts/model_pipeline.pkl"
spam_p   = os.environ.get("SPAM_PKL")   or "models/spam/artifacts/model_pipeline.pkl"
intent_p = str(Path(intent_p).expanduser())
spam_p   = str(Path(spam_p).expanduser())

rep = {"intent": {"path": intent_p}, "spam": {"path": spam_p}}

for key, p in rep.items():
    try:
        pipe = load_any(p["path"])
        p.update(probe(pipe))
        p["smoke"] = predict_safe(pipe, [
            "FREE $$$ click here!!!",
            "請問申請資料要怎麼修改？",
            "我要投訴服務品質"
        ])
    except Exception as e:
        p["error"] = f"load_failed: {e}\n{traceback.format_exc()}"

(OUTD/"report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), "utf-8")
print(json.dumps(rep, ensure_ascii=False, indent=2))
