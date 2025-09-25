from __future__ import annotations
import sys, json, re
from pathlib import Path

DEFAULT_ML_PKL = Path("artifacts/intent_pro_cal.pkl")
FEATURE_SPEC   = Path("artifacts_prod/intent_feature_spec.json")
LABEL_MAP      = Path("artifacts_prod/intent_label_map.json")
NAMES_JSON     = Path("artifacts_prod/intent_names.json")

def _alias_main_to_sma_features():
    import importlib
    from pathlib import Path as _P
    src = _P('src').resolve()
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    try:
        sf = importlib.import_module('sma_features')
    except Exception:
        sf = importlib.import_module('src.sma_features')
    # 讓 pickle 找得到 __main__.* 以及 sma_features.*
    sys.modules.setdefault('sma_features', sf)
    sys.modules['__main__'] = sf
    return sf

def _load_joblib(pkl: Path):
    try:
        import joblib
    except Exception as e:
        raise RuntimeError("缺少 joblib / scikit-learn，請先安裝：pip install -U scikit-learn joblib") from e
    return joblib.load(pkl)

def _looks_like_estimator(x) -> bool:
    return hasattr(x, "predict") or hasattr(x, "fit")

def _unwrap_pipeline(obj, _depth=0):
    """嘗試從 dict/tuple/各種 wrapper 裡找出真正能 predict 的 estimator/pipeline"""
    if _depth > 5:
        return obj
    if _looks_like_estimator(obj):
        return obj
    # 常見屬性
    for attr in ("best_estimator_", "estimator", "estimator_", "pipeline", "pipeline_", "model", "model_", "classifier", "classifier_", "clf", "final_estimator"):
        if hasattr(obj, attr):
            try:
                inner = getattr(obj, attr)
                return _unwrap_pipeline(inner, _depth+1)
            except Exception:
                pass
    # dict 包裝
    if isinstance(obj, dict):
        for k in ("pipeline", "pipe", "model", "estimator", "best_estimator_", "clf", "final"):
            if k in obj:
                return _unwrap_pipeline(obj[k], _depth+1)
        for v in obj.values():
            if _looks_like_estimator(v):
                return _unwrap_pipeline(v, _depth+1)
    # list/tuple 包裝
    if isinstance(obj, (list, tuple)):
        for v in obj:
            if _looks_like_estimator(v):
                return _unwrap_pipeline(v, _depth+1)
    return obj

def load_names() -> list[str]:
    if not NAMES_JSON.exists():
        return []
    return json.loads(NAMES_JSON.read_text(encoding="utf-8")).get("names", [])

def ensure_label_map(pipeline) -> dict:
    names = load_names()
    classes = []
    # 先從 pipeline 自身
    if hasattr(pipeline, "classes_"):
        classes = list(getattr(pipeline, "classes_"))
    # 再嘗試 named_steps 的末端分類器
    if (not classes) and hasattr(pipeline, "named_steps"):
        for key in ("clf", "classifier", "final", "estimator"):
            est = pipeline.named_steps.get(key)  # type: ignore
            if est is not None and hasattr(est, "classes_"):
                classes = list(est.classes_)
                break
    m = {}
    if classes:
        if names and set(classes) == set(names):
            m = {str(c): str(c) for c in classes}
        elif names and len(classes) == len(names):
            m = {str(c): str(n) for c, n in zip(classes, names)}
        else:
            m = {str(c): str(c) for c in classes}
    LABEL_MAP.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    return m

def _read_spec() -> dict:
    if FEATURE_SPEC.exists():
        try:
            return json.loads(FEATURE_SPEC.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"dims": {"prio": 0, "bias": 0}}

def _write_spec(spec: dict):
    FEATURE_SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

def _sample_email():
    return {"subject": "報價 單價:100 數量:2", "body": "ticket:TS-1234 規則詢問 資料異動 order:ORD-9"}

def _input_variants():
    e = _sample_email()
    combo = (e.get("subject","") + " " + e.get("body","")).strip()
    return [
        [e],
        [{"text": combo}],
        [combo],
        [e.get("subject","")],
        [e.get("body","")],
    ]

def _try_predict_once(pipe):
    last = ""
    for X in _input_variants():
        try:
            try:
                _ = pipe.predict_proba(X)
            except Exception:
                _ = pipe.predict(X)
            return True, "ok"
        except Exception as e:
            last = str(e)
    return False, last

def load_intent_pipeline(pkl: Path = DEFAULT_ML_PKL, auto_calibrate: bool = True):
    if not pkl.exists():
        raise FileNotFoundError(f"找不到模型：{pkl}")
    _alias_main_to_sma_features()
    raw = _load_joblib(pkl)
    pipe = _unwrap_pipeline(raw)
    ensure_label_map(pipe)

    if auto_calibrate:
        ok, msg = _try_predict_once(pipe)
        if not ok:
            # 解析「X has N features, but expects M」
            m = re.search(r"X has (\d+) features?, but (?:this )?estimator expects (\d+)", msg)
            if m:
                got, exp = int(m.group(1)), int(m.group(2))
                diff = exp - got
                if diff != 0:
                    spec = _read_spec()
                    # 策略：優先補到 prio，否則補到 bias
                    if spec["dims"].get("prio", 0) == 0:
                        spec["dims"]["prio"] = max(0, spec["dims"].get("prio", 0) + diff)
                    else:
                        spec["dims"]["bias"] = max(0, spec["dims"].get("bias", 0) + diff)
                    _write_spec(spec)
                    # 重新 alias + 重新載模型（讓新 spec 生效）
                    _alias_main_to_sma_features()
                    raw = _load_joblib(pkl)
                    pipe = _unwrap_pipeline(raw)
                    ok2, msg2 = _try_predict_once(pipe)
                    if not ok2:
                        raise RuntimeError(f"特徵維度仍不符：{msg2}")
            else:
                raise RuntimeError(f"pipeline 無法預測：{msg}")
    return pipe

def predict(email: dict, pkl: Path = DEFAULT_ML_PKL) -> dict:
    pipe = load_intent_pipeline(pkl, auto_calibrate=True)
    lm = json.loads(LABEL_MAP.read_text(encoding="utf-8")) if LABEL_MAP.exists() else {}
    # 取 top1，能 proba 就用，否則退回 predict
    try:
        probs = pipe.predict_proba([email])[0]
        cls = getattr(pipe, "classes_", None)
        if cls is None and hasattr(pipe, "named_steps"):
            for key in ("clf", "classifier", "final", "estimator"):
                est = pipe.named_steps.get(key)  # type: ignore
                if est is not None and hasattr(est, "classes_"):
                    cls = est.classes_
                    break
        if cls is None:
            # 無 classes_ 就直接用 predict
            raise AttributeError("no classes_")
        import numpy as np  # 確保有
        top_i = int(probs.argmax())
        raw = str(cls[top_i])
        conf = float(probs[top_i])
    except Exception:
        pred = pipe.predict([email])[0]
        raw, conf = str(pred), 1.0
    name = lm.get(raw, raw)
    return {"intent_raw": raw, "intent_name": name, "confidence": conf}
