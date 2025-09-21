#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, glob, os, time
from pathlib import Path

ROOT=Path(".").resolve()
TS=time.strftime("%Y%m%dT%H%M%S")
EVALS=sorted(glob.glob("reports_auto/eval/*/metrics_after_threshold_and_rules.md"))
if not EVALS: 
    print("[WARN] no eval reports"); exit(0)
rep=EVALS[-1]
# 簡單解析 macro F1
macro=None
for ln in open(rep,"r",encoding="utf-8"):
    if "macro_f1_after_threshold_and_rules" in ln:
        macro=float(ln.strip().split(":")[-1])
        break

# Gate
gate_macro=0.55
if macro is not None and macro>=gate_macro:
    print(f"[OK] gate pass: macroF1={macro} >= {gate_macro}")
    # 如需覆寫 thresholds，可在此讀取建議表並寫回
else:
    print(f"[SKIP] gate not met: macroF1={macro} < {gate_macro}")
