# -*- coding: utf-8 -*-
import os, sys, json, time
from pathlib import Path
from tools.model_bundle import IntentBundle

bundledir = Path(os.environ.get("SMA_BUNDLE_DIR","bundles/intent_v1/LATEST"))
TS = time.strftime("%Y%m%dT%H%M%S")
OUTD = Path("reports_auto/status")/f"PREFLIGHT_{TS}"; OUTD.mkdir(parents=True, exist_ok=True)
rep = {"bundle_dir": str(bundledir), "ok": False, "error": None}
try:
    B = IntentBundle(bundledir)
    B.preflight()
    rep["ok"] = True
except Exception as e:
    rep["error"] = f"{type(e).__name__}: {e}"
(OUTD/"summary.json").write_text(json.dumps(rep,ensure_ascii=False,indent=2), encoding="utf-8")
print("[PREFLIGHT]", rep)
if not rep["ok"]: sys.exit(2)
