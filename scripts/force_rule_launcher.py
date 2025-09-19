#!/usr/bin/env python3
import os, sys, importlib.util, types, re

# 確保 'tools' 套件可載
if "tools" not in sys.modules:
    pkg_path = os.path.join(os.getcwd(), "tools", "__init__.py")
    spec_pkg = importlib.util.spec_from_file_location("tools", pkg_path)
    pkg = importlib.util.module_from_spec(spec_pkg); spec_pkg.loader.exec_module(pkg)
    sys.modules["tools"] = pkg

# 載入原始 pipeline_baseline 做為 orig
orig_path = os.path.join(os.getcwd(), "tools", "pipeline_baseline.py")
spec_orig = importlib.util.spec_from_file_location("_pipeline_baseline_orig", orig_path)
orig = importlib.util.module_from_spec(spec_orig); spec_orig.loader.exec_module(orig)

# 準備 runtime 規則
_predict = None
rules_path = os.environ.get("SMA_RULES_SRC","")
if rules_path and os.path.isfile(rules_path):
    try:
        spec_rules = importlib.util.spec_from_file_location("sma_runtime_rules", rules_path)
        rm = importlib.util.module_from_spec(spec_rules); spec_rules.loader.exec_module(rm)
        if hasattr(rm, "predict_one"):
            _predict = rm.predict_one
        elif hasattr(rm, "predict"):
            _predict = lambda t: (rm.predict([t]) or ["other"])[0]
    except Exception:
        _predict = None

# 建 proxy：照搬 orig 內容，只覆蓋 classify_rule / extract_slots_rule
proxy = types.ModuleType("tools.pipeline_baseline")
for k, v in orig.__dict__.items():
    if k not in ("classify_rule", "extract_slots_rule"):
        setattr(proxy, k, v)

def _classify_rule(email=None, contract=None, **kw):
    txt = email.get("text","") if isinstance(email, dict) else (email or "")
    if _predict:
        try: return _predict(txt) or "other"
        except Exception: pass
    try: return orig.classify_rule(email=email, contract=contract, **kw)
    except TypeError: return orig.classify_rule(email if email is not None else {"text": txt}, contract)

def _extract_slots_rule(email=None, intent=None, **kw):
    txt = email.get("text","") if isinstance(email, dict) else (email or "")
    s = {"price": None, "qty": None, "id": None}
    m = (re.search(r'(?:NTD|NT\$|\$)?\s*([0-9][\d,\.]{2,})\s*(?:元)?', txt, re.I) or
         re.search(r'([0-9][\d,\.]{2,})\s*(?:元|NTD|NT\$|\$)', txt, re.I))
    if m: s["price"] = m.group(1).replace(",", "")
    m = re.search(r'(?:數量|各|共|x|×)\s*([0-9]+)', txt, re.I)
    if m: s["qty"] = int(m.group(1))
    m = re.search(r'\b([A-Z]{2,}-?\d{4,})\b', txt)
    if m: s["id"] = m.group(1)
    return s

proxy.classify_rule = _classify_rule
proxy.extract_slots_rule = _extract_slots_rule

# 注入，之後 api_server import 的就是這版
sys.modules["tools.pipeline_baseline"] = proxy

# 啟 API（其模組頂層會啟動 HTTPServer）
import tools.api_server  # noqa
