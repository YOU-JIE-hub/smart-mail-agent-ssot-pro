from __future__ import annotations
import os, sys, json, re, types
from pathlib import Path

DEFAULT_ML_PKL = Path(os.environ.get("SMA_INTENT_ML_PKL") or "artifacts/intent_pro_cal.pkl")
LABEL_MAP      = Path("artifacts_prod/intent_label_map.json")

# ---- import helpers (kept simple & robust) ----
def _alias_main_to_sma_features():
    import importlib
    src = Path("src").resolve()
    if str(src) not in sys.path: sys.path.insert(0, str(src))
    try:
        sf = importlib.import_module("sma_features")
    except Exception:
        # fallback: empty shims
        mod = types.ModuleType("sma_features")
        def _zeros(X, d=0):
            try:
                import numpy as np
                return np.zeros((len(X), d), dtype="float32")
            except Exception:
                return [[0.0]*d for _ in range(len(X))]
        mod.rules_feat = lambda X: [{} for _ in X]
        mod.prio_feat  = lambda X: _zeros(X, 0)
        mod.bias_feat  = lambda X: _zeros(X, 0)
        sf = mod
    sys.modules["sma_features"] = sf
    sys.modules["__main__"]     = sf

def _load_joblib(pkl: Path):
    import joblib
    return joblib.load(pkl)

def _unwrap_pipeline(obj):
    # joblib 可能包了 {"pipeline": Pipeline(...)} 的 dict
    if isinstance(obj, dict) and "pipeline" in obj:
        return obj["pipeline"]
    return obj

# ---- 中文→英文提示詞（不改模型，只改輸入文字）----
_HINTS = [
    (r"(報價|報價單|單價|詢價|出價|報價請求)",        ["quote","quotation","pricing","price"]),
    (r"(投訴|客訴|抱怨|申訴|退款|退費|退貨|chargeback)", ["complaint","refund","chargeback","return"]),
    (r"(技術支援|技支|當機|故障|掛了|錯誤|bug|ticket|工單)", ["tech_support","bug","ticket","issue"]),
    (r"(規則|政策|條款|policy|規範|合規|退貨政策|SLA)",    ["policy","rule","terms","policy_qa"]),
    (r"(資料異動|更新資料|變更|更正|改地址|改電話|改名|profile|update)", ["profile_update","account_update","update"]),
    (r"(一般|詢問|請益|您好|哈囉|hello|hi)",             ["other","general","reply"]),
]

def _normalize_text(text: str) -> str:
    txt = text or ""
    boost = []
    lo = txt.lower()
    for pat, toks in _HINTS:
        if re.search(pat, txt, flags=re.I):
            boost.extend(toks)
    # 關鍵字段映射（提高英文詞出現率）
    if re.search(r"(單價|price)[：: ]?(\d+)", txt, flags=re.I):
        boost.extend(["price"])
    if re.search(r"(數量|qty)[：: ]?(\d+)", txt, flags=re.I):
        boost.extend(["qty"])
    if re.search(r"(ticket|工單|order|單號)[：: ]?([A-Za-z0-9_-]{3,})", txt, flags=re.I):
        boost.extend(["ticket","order"])
    if boost:
        txt = f"{txt}\n" + " ".join(sorted(set(boost)))
    return txt

def _to_text(email: dict) -> str:
    if isinstance(email, str): 
        return _normalize_text(email)
    if isinstance(email, dict):
        subj = str(email.get("subject","") or "")
        body = str(email.get("body","") or email.get("text","") or "")
        return _normalize_text((subj + "\n" + body).strip())
    # tuple/list: 取前兩段拼起來
    if isinstance(email, (list, tuple)) and email:
        parts = [str(x) for x in email if isinstance(x,(str,bytes))]
        return _normalize_text("\n".join(parts))
    return _normalize_text(str(email))

def predict(email: dict, pkl: Path = DEFAULT_ML_PKL) -> dict:
    _alias_main_to_sma_features()
    pipe = _unwrap_pipeline(_load_joblib(pkl))

    text = _to_text(email)
    X = [text]

    # 推斷 classes_
    classes = []
    for attr in ("classes_",):
        if hasattr(pipe, attr):
            classes = list(getattr(pipe, attr)); break
    if not classes and getattr(pipe, "named_steps", None):
        for k in ("clf","final","classifier","estimator"):
            est = pipe.named_steps.get(k)
            if est is not None and hasattr(est, "classes_"):
                classes = list(est.classes_); break

    # 推理
    try:
        probs = pipe.predict_proba(X)[0]
        import numpy as np
        top_i = int(np.argmax(probs))
        raw   = str(classes[top_i]) if classes else str(top_i)
        conf  = float(probs[top_i])
    except Exception:
        pred  = pipe.predict(X)[0]
        raw   = str(pred)
        conf  = 1.0

    # label map 映射（英→中）
    label_map = {}
    if LABEL_MAP.exists():
        try:
            label_map = json.loads(LABEL_MAP.read_text(encoding="utf-8"))
        except Exception:
            label_map = {}
    name = label_map.get(raw, raw)
    return {"intent_raw": raw, "intent_name": name, "confidence": conf}
