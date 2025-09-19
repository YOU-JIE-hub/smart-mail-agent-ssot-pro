from __future__ import annotations
from tools.ml_io import load_intent_pipeline, FEATURE_SPEC, LABEL_MAP, DEFAULT_ML_PKL
import json
pipe=load_intent_pipeline(DEFAULT_ML_PKL, auto_calibrate=True)
spec=json.loads(FEATURE_SPEC.read_text(encoding="utf-8")) if FEATURE_SPEC.exists() else {}
lm  =json.loads(LABEL_MAP.read_text(encoding="utf-8")) if LABEL_MAP.exists() else {}
print("[SPEC]", json.dumps(spec, ensure_ascii=False))
print("[LABEL_MAP]", json.dumps(lm, ensure_ascii=False))
