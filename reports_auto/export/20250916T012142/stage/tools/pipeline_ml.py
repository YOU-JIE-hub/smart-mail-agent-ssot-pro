
from __future__ import annotations
from pathlib import Path
import re, json
from typing import Any, Dict, Tuple
from tools.ml_compat import alias_main, joblib_load

alias_main()

_DEF_MAP = {
  "biz_quote": "報價",
  "tech_support": "技術支援",
  "policy_qa": "規則詢問",
  "profile_update": "資料異動",
  "complaint": "投訴",
  "other": "一般回覆",
}
def _load_label_map()->Dict[str,str]:
    cfg = Path("configs/intent_label_map.json")
    if cfg.exists():
        try: return json.loads(cfg.read_text(encoding="utf-8"))
        except Exception: pass
    return dict(_DEF_MAP)

_LABEL_MAP = _load_label_map()

_EST = None
_EST_PATHS = [
    Path((Path.cwd()/ "artifacts/intent_pro_cal.pkl")),
    Path((Path.cwd()/ "artifacts_prod/model_pipeline.pkl")),
]
def _get_est():
    global _EST
    if _EST is not None: return _EST
    for p in _EST_PATHS:
        if p.exists():
            obj = joblib_load(str(p))
            est = obj
            if isinstance(obj, dict):
                for k in ("pipeline","model","clf","estimator","sk_model","pipe"):
                    if k in obj and hasattr(obj[k],"predict"):
                        est = obj[k]; break
            _EST = est; return _EST
    raise FileNotFoundError("No estimator pickle found in artifacts/ or artifacts_prod/")

_rx_tid = re.compile(r'\b(?:TS|BUG|CR|INC|SR|ORD|CASE)-?\d+\b', re.I)
_rx_ws  = re.compile(r'\s+')

def _fw2hw(s:str)->str:
    return s.translate(str.maketrans({**{chr(0xFF10+i):str(i) for i in range(10)},
                                      0xFF24:"$", 0xFF04:"$"}))

def _compose(email: Dict[str,str]) -> str:
    subj = email.get("subject","") or ""
    body = email.get("body","") or ""
    t = (subj + "\n" + body).strip()
    t = _fw2hw(t)
    t = t.lower()
    t = _rx_tid.sub(" tid ", t)
    t = _rx_ws.sub(" ", t).strip()
    return t

def _top2_from_proba(est, X: str):
    # 預設：單句 -> [text]；拿 predict_proba
    if hasattr(est, "predict_proba"):
        import numpy as np
        P = est.predict_proba([X])[0]
        cls = getattr(est, "classes_", None)
        if cls is None: return None
        pairs = list(zip([str(c) for c in cls], [float(x) for x in P]))
        pairs.sort(key=lambda x: x[1], reverse=True)
        top1, top2 = pairs[0], (pairs[1] if len(pairs)>1 else (pairs[0][0], 0.0))
        margin = float(top1[1] - top2[1])
        # 中文映射
        def zh(c): return _LABEL_MAP.get(c, c)
        return {
            "top1": {"en": top1[0], "zh": zh(top1[0]), "conf": top1[1]},
            "top2": {"en": top2[0], "zh": zh(top2[0]), "conf": top2[1]},
            "margin": margin,
            "all": [{"en": c, "zh": zh(c), "conf": float(p)} for c,p in pairs]
        }
    return None

def classify_ml(email: Dict[str,str]):
    """回傳 (zh, conf, raw)，raw 內含 top2/margin/all（若模型支援 predict_proba）。"""
    est = _get_est()
    x = _compose(email)
    # 先求 top1
    y = est.predict([x])[0]
    en = str(y)
    zh = _LABEL_MAP.get(en, en)
    conf = None
    raw = _top2_from_proba(est, x)
    if raw is not None:
        conf = float(raw["top1"]["conf"])
    else:
        # 沒有 predict_proba 時，用 None；呼叫端可降級處理
        conf = None
        raw = {"top1":{"en":en,"zh":zh,"conf":None},"top2":None,"margin":None,"all":[]}
    return zh, conf, raw
