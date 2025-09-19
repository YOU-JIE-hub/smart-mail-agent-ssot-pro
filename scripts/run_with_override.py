#!/usr/bin/env python3
import os, sys, importlib.util, types, re, runpy, traceback, faulthandler
faulthandler.enable()

def load_rules_predict():
    path = os.environ.get("SMA_RULES_SRC","")
    if not path: return None
    try:
        spec = importlib.util.spec_from_file_location("sma_runtime_rules", path)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        if hasattr(m, "predict_one"): return m.predict_one
        if hasattr(m, "predict"): return lambda t: (m.predict([t]) or ["other"])[0]
    except Exception:
        return None

def patch_pipeline():
    try:
        import tools.pipeline_baseline as P
    except Exception:
        return
    predict = load_rules_predict()
    if predict:
        def _classify_rule(email=None, contract=None, **kw):
            text = ""
            if isinstance(email, dict): text = email.get("text","") or ""
            elif isinstance(email, str): text = email
            return predict(text) or "other"
        P.classify_rule = _classify_rule

    def _extract_slots_rule(email=None, intent=None, **kw):
        txt = email.get("text","") if isinstance(email, dict) else (email or "")
        s={"price":None,"qty":None,"id":None}
        m = (re.search(r"(?:\\$|NTD?\\s*)\\s*([0-9][\\d,\\.]*)", txt, re.I) or
             re.search(r"([0-9][\\d,\\.]*)\\s*(?:元|NTD?|\\$)", txt, re.I))
        if m: s["price"] = m.group(1).replace(",","")
        m = re.search(r"(?:數量|各|共|x)\\s*([0-9]+)", txt, re.I)
        if m: s["qty"] = int(m.group(1))
        m = re.search(r"\\b([A-Z]{2,}-?\\d{4,})\\b", txt)
        if m: s["id"] = m.group(1)
        return s
    try:
        import tools.pipeline_baseline as P2
        P2.extract_slots_rule = _extract_slots_rule
    except Exception:
        pass

def main():
    try:
        patch_pipeline()
        runpy.run_module("tools.api_server", run_name="__main__")
    except SystemExit:
        raise
    except Exception as e:
        print("[LAUNCHER] fatal:", e, file=sys.stderr)
        traceback.print_exc()
        raise

if __name__ == "__main__": main()
