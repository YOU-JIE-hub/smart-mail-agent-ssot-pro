#!/usr/bin/env python3
import os, sys, importlib.util, types, re, runpy
ROOT = os.getcwd()

# 載入原版 pipeline
orig_path = os.path.join(ROOT, "tools", "pipeline_baseline.py")
spec = importlib.util.spec_from_file_location("tools.pipeline_baseline.__orig", orig_path)
orig = importlib.util.module_from_spec(spec); spec.loader.exec_module(orig)

# 包裝一份，預設繼承全部
wrap = types.ModuleType("tools.pipeline_baseline")
wrap.__dict__.update(orig.__dict__)

# 讀 runtime 規則（可選）
predict = None
rules = os.environ.get("SMA_RULES_SRC", "")
if rules and os.path.isfile(rules):
    try:
        rspec = importlib.util.spec_from_file_location("sma_runtime_rules", rules)
        rm = importlib.util.module_from_spec(rspec); rspec.loader.exec_module(rm)
        if hasattr(rm, "predict_one"): predict = rm.predict_one
        elif hasattr(rm, "predict"):    predict = lambda t: (rm.predict([t]) or ["other"])[0]
    except Exception:
        predict = None

def classify_rule(email, contract, **kw):
    text = email.get("text","") if isinstance(email, dict) else (email or "")
    if predict:
        return predict(text) or "other"
    return orig.classify_rule(email=email, contract=contract, **kw)

def extract_slots_rule(email, intent, **kw):
    txt = email.get("text","") if isinstance(email, dict) else (email or "")
    s = {"price": None, "qty": None, "id": None}
    m = (re.search(r'(?:\$|NTD?\s*)([0-9][\d,\.]*)', txt, re.I) or
         re.search(r'([0-9][\d,\.]*)\s*(?:元|NTD?|\$)', txt, re.I))
    if m:
        v = m.group(1).replace(",", "")
        try: s["price"] = float(v)
        except: s["price"] = v
    m = re.search(r'(?:數量|各|共|x)\s*([0-9]+)', txt, re.I)
    if m:
        try: s["qty"] = int(m.group(1))
        except: s["qty"] = m.group(1)
    m = re.search(r'\b([A-Z]{2,}-?\d{4,})\b', txt)
    if m: s["id"] = m.group(1)
    return s

wrap.classify_rule = classify_rule
wrap.extract_slots_rule = extract_slots_rule
sys.modules["tools.pipeline_baseline"] = wrap

# 進入原本 API server
runpy.run_module("tools.api_server", run_name="__main__")
