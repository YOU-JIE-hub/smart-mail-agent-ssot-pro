#!/usr/bin/env python3
import os, json, importlib.util, sys
from pathlib import Path
ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot")
ok=True
def need(p, name):
    global ok
    if p.exists(): print(f"[OK] {name}: {p}")
    else: print(f"[MISS] {name}: {p}"); ok=False
need(ROOT/"artifacts_prod"/"model_pipeline.pkl","Spam model")
need(ROOT/"artifacts_prod"/"ens_thresholds.json","Spam thresholds")
if (ROOT/"artifacts_prod"/"ens_thresholds.json").exists():
    try:
        th=json.loads((ROOT/"artifacts_prod"/"ens_thresholds.json").read_text("utf-8")); float(th["spam"])
    except Exception as e: print(f"[ERR] spam thresholds invalid: {e}"); ok=False
need(ROOT/"artifacts"/"intent_pro_cal.pkl","Intent model")
need(ROOT/"reports_auto"/"intent_thresholds.json","Intent thresholds")
if (ROOT/"reports_auto"/"intent_thresholds.json").exists():
    try:
        th=json.loads((ROOT/"reports_auto"/"intent_thresholds.json").read_text("utf-8"))
        for k in ["報價","技術支援","投訴","規則詢問","資料異動","其他"]: float(th[k])
    except Exception as e: print(f"[ERR] intent thresholds invalid: {e}"); ok=False
need(ROOT/"kie"/"config.json","KIE config")
need(ROOT/"kie"/"infer.py","KIE infer.py")
if (ROOT/"kie"/"infer.py").exists():
    try:
        spec=importlib.util.spec_from_file_location("kie_infer", ROOT/"kie"/"infer.py")
        m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        assert hasattr(m,"extract")
    except Exception as e: print(f"[ERR] kie infer invalid: {e}"); ok=False
print("[RESULT]", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
