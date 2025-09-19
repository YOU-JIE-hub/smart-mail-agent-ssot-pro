#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"; RUN="reports_auto/eval_fix/${TS}"
LOG="$RUN/run.log"; ERR="$RUN/tri_eval.err"; PY_LAST="$RUN/py_last_trace.txt"
mkdir -p "$RUN"; exec > >(tee -a "$LOG") 2>&1
trap 'ec=${1:-$?}; echo "exit_code=$ec" > "$ERR"; echo "[PATHS]"; echo "  RUN = $(cd "$RUN"&&pwd)"; echo "  LOG = $(cd "$RUN"&&pwd)/run.log"; echo "  ERR = $(cd "$RUN"&&pwd)/tri_eval.err"; echo "  PY_LAST = $(cd "$RUN"&&pwd)/py_last_trace.txt"; echo "  RESULT = $(cd "$RUN"&&pwd)/tri_results_fixed.json"; exit 0' ERR
set -a; . scripts/env.default 2>/dev/null || true; set +a
export PYTHONPATH="src:vendor:${PYTHONPATH:-}"
PYBIN="./.venv/bin/python"; [ -x "$PYBIN" ] || PYBIN="$(command -v python)"
DATA="data/intent_eval/dataset.cleaned.jsonl"
[ -f "$DATA" ] || { echo "[FATAL] $DATA not found"; exit 0; }
echo "[*] PYBIN=$PYBIN"; echo "[*] DATA=$DATA"; echo "[*] PKL=$SMA_INTENT_ML_PKL"; echo "[*] RULES_SRC=$SMA_RULES_SRC (bind to __main__.rules_feat)"
"$PYBIN" - "$DATA" "$SMA_INTENT_ML_PKL" "$SMA_RULES_SRC" "$RUN/tri_results_fixed.json" <<'PY'
import sys, json, importlib.util, __main__, joblib, pathlib, time, numpy as np
from vendor.sma_tools.label_map import normalize_labels
data, pkl, rules_src, out = sys.argv[1:5]
spec = importlib.util.spec_from_file_location("rt", rules_src)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
setattr(__main__, "rules_feat", getattr(m,"rules_feat", None))
obj=joblib.load(pkl)
def pick(o):
    if hasattr(o,"predict"): return o
    if isinstance(o,dict):
        for k in ("pipe","pipeline","estimator","model"):
            if k in o and o[k] is not None: return pick(o[k])
    if isinstance(o,(list,tuple)) and o: return pick(o[0])
    raise SystemExit("no predictor inside pickle")
est = pick(obj)
texts=[]; ys=[]
with open(data,"r",encoding="utf-8") as f:
    for line in f:
        j=json.loads(line); texts.append(j.get("text","")); ys.append(j.get("label","other"))
Y = normalize_labels(ys,"en")
t0=time.time(); yp=[str(y) for y in est.predict(texts)]; t1=time.time()
from sklearn.metrics import f1_score
acc = float(np.mean([a==b for a,b in zip(Y, yp)]))
mf1 = float(f1_score(Y, yp, average="macro"))
res={"n":len(texts),"runs":[{"route":"ml","pred":yp,"latency_ms":int((t1-t0)*1000),"report":{"accuracy":acc,"macro_f1":mf1}}]}
pathlib.Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[OK] wrote: {out}")
PY
echo "[PATHS]"; echo "  RUN = $(cd "$RUN"&&pwd)"; echo "  LOG = $(cd "$RUN"&&pwd)/run.log"; echo "  ERR = $(cd "$RUN"&&pwd)/tri_eval.err"; echo "  PY_LAST = $(cd "$RUN"&&pwd)/py_last_trace.txt"; echo "  RESULT = $(cd "$RUN"&&pwd)/tri_results_fixed.json"
