#!/usr/bin/env python3
import os, sys, importlib, importlib.util, runpy, re

def _load_predict():
    path = os.environ.get("SMA_RULES_SRC","")
    if not (path and os.path.isfile(path)):
        return None
    try:
        sp = importlib.util.spec_from_file_location("sma_runtime_rules", path)
        m  = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
        if hasattr(m, "predict_one") and callable(m.predict_one):
            return m.predict_one
        if hasattr(m, "predict") and callable(m.predict):
            return lambda t: (m.predict([t]) or ["other"])[0]
    except Exception:
        return None
    return None

# 先 import 原始 pipeline
P = importlib.import_module("tools.pipeline_baseline")
_predict = _load_predict()

# 備份原函式
_classify_orig = getattr(P, "classify_rule", None)
_extract_orig  = getattr(P, "extract_slots_rule", None)

# 規則：先用 runtime 規則，失敗回退原本
def classify_rule(email=None, contract=None, **kw):
    text = ""
    if isinstance(email, dict): text = email.get("text","") or ""
    elif isinstance(email, str): text = email
    if _predict:
        try:
            return _predict(text) or "other"
        except Exception:
            pass
    if _classify_orig:
        return _classify_orig(email=email, contract=contract, **kw)
    return "一般回覆"

# 穩定抽槽（price/qty/id）
_PRICE_RES = [
    re.compile(r"(?:NTD|NT\$|\\$)\\s*([0-9][\\d,\\.]*)", re.I),
    re.compile(r"([0-9][\\d,\\.]*)\\s*(?:元|塊|NTD|NT\\$|\\$)", re.I),
]
_QTY_RE = re.compile(r"(?:數量|各|共|x|×)\\s*([0-9]+)", re.I)
_ID_RE  = re.compile(r"\\b([A-Z]{2,}-?\\d{4,})\\b")

def extract_slots_rule(email=None, intent=None, **kw):
    txt = email.get("text","") if isinstance(email, dict) else (email or "")
    try:
        s = {"price": None, "qty": None, "id": None}
        price=None
        for r in _PRICE_RES:
            m = r.search(txt)
            if m:
                price = m.group(1).replace(",", "")
                break
        if price: s["price"] = price
        m = _QTY_RE.search(txt)
        if m: s["qty"] = int(m.group(1))
        m = _ID_RE.search(txt)
        if m: s["id"] = m.group(1)
        return s
    except Exception:
        if _extract_orig:
            return _extract_orig(email=email, intent=intent, **kw)
        return {"price": None, "qty": None, "id": None}

# 打補丁
P.classify_rule = classify_rule
P.extract_slots_rule = extract_slots_rule

print("[PATCH] tools.pipeline_baseline -> classify_rule/extract_slots_rule patched", flush=True)

# 起 API（與補丁在同一進程）
runpy.run_module("tools.api_server", run_name="__main__")
