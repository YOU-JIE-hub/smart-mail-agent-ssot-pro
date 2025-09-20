import os, sys, json, time, traceback
from pathlib import Path
from datetime import datetime
import joblib

ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / f"reports_auto/spam_smoke_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
OUTD.mkdir(parents=True, exist_ok=True)
RPT = OUTD / "report.json"

MODEL = os.environ.get("SPAM_PKL") or sys.argv[1] if len(sys.argv)>1 else None
if not MODEL: 
    print("[FATAL] no SPAM_PKL given", file=sys.stderr); sys.exit(64)
MODEL = str(Path(MODEL).expanduser().resolve())

# ---- shims for old pickles ----
try:
    from vendor import rules_features as RF
    sys.modules.setdefault("__main__", sys.modules["builtins"])  # ensure __main__ exists
    setattr(sys.modules["__main__"], "rules_feat", getattr(RF, "rules_feat", lambda x: {}))
    setattr(sys.modules["__main__"], "rules_feat_func", getattr(RF, "rules_feat_func", getattr(RF, "rules_feat", lambda x: {})))
except Exception:
    # 最少也給個空函式，不然舊 pkl 會炸
    def _empty(x): return {}
    sys.modules.setdefault("__main__", sys.modules["builtins"])
    setattr(sys.modules["__main__"], "rules_feat", _empty)
    setattr(sys.modules["__main__"], "rules_feat_func", _empty)

info = {"model_path": MODEL, "ok": False, "error": None, "classes": None, "vocab_size": None, "pipeline_steps": None, "samples": []}
try:
    obj = joblib.load(MODEL)
    pipe = obj
    # 常見情況：有些存的是 dict 或 {"pipeline": pipe}
    if isinstance(obj, dict):
        pipe = obj.get("pipeline", obj.get("model", obj))
    # 取類別與向量器 vocab
    steps = None
    try:
        if hasattr(pipe, "steps"):
            steps = [name for name,_ in pipe.steps]
            # 嘗試找 vectorizer 名稱
            for k, v in pipe.named_steps.items():
                if hasattr(v, "vocabulary_"):
                    info["vocab_size"] = len(v.vocabulary_)
                    break
    except Exception:
        pass
    info["pipeline_steps"] = steps
    # 取 classes_
    try:
        # 先找最後一個有 classes_ 的步驟
        last = getattr(pipe, "named_steps", {}).get(next(reversed(pipe.named_steps)) if hasattr(pipe, "named_steps") else "", None)
        clf = None
        if last is not None and hasattr(last, "classes_"):
            clf = last
        elif hasattr(pipe, "classes_"):
            clf = pipe
        if clf is not None:
            info["classes"] = list(map(str, clf.classes_))
    except Exception:
        pass

    # 冒煙測試
    samples = [
        "FREE $$$ click here!!!",
        "請問申請資料要怎麼修改？",
        "想了解一下報價與合約",
        "系統登入不了，一直顯示錯誤",
        "我要投訴服務品質"
    ]
    preds = []
    try:
        y = pipe.predict(samples)
        preds = list(map(lambda x: str(x), y))
    except Exception as e:
        info["error"] = f"predict_failed: {e}"
    info["samples"] = [{"text": s, "pred": p} for s,p in zip(samples, preds)]
    info["ok"] = info["error"] is None
except Exception as e:
    info["error"] = f"load_failed: {e}\n{traceback.format_exc()}"

RPT.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(info, ensure_ascii=False, indent=2))
