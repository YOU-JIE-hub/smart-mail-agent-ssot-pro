#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
LAST="$(ls -1dt reports_auto/eval_fix/2* reports_auto/eval/2* 2>/dev/null | head -n1 || true)"
[ -n "$LAST" ] || { echo "[FATAL] no eval dir under reports_auto/eval_fix or reports_auto/eval"; exit 0; }
RES="$LAST/tri_results_fixed.json"; [ -f "$RES" ] || RES="$LAST/tri_results.json"
[ -f "$RES" ] || { echo "[FATAL] no tri_results json in $LAST"; exit 0; }
TS="$(basename "$LAST")"; MD="reports_auto/status/INTENTS_SUMMARY_${TS}.md"
PYBIN="./.venv/bin/python"; [ -x "$PYBIN" ] || PYBIN="$(command -v python)"
"$PYBIN" - "$RES" "$MD" <<'PY'
import sys, json, pathlib
res = pathlib.Path(sys.argv[1]); md = pathlib.Path(sys.argv[2])
J = json.loads(res.read_text(encoding="utf-8")); runs = J.get("runs", [])
m = { r.get("route"): r for r in runs }
ml = m.get("ml") or {}
def pick(d,k,default=0.0): return float(d.get("report",{}).get(k, default))
acc = pick(ml, "accuracy"); mf1 = pick(ml, "macro_f1"); lat = int(ml.get("latency_ms",0))
md.write_text(f"# INTENT TRI-EVAL SUMMARY ({res.parent.name})\n\n"
              f"- RESULT_JSON: {res}\n\n"
              "| route | accuracy | macro F1 | latency ms |\n|---|---:|---:|---:|\n"
              f"| ml.classify | {acc:.4f} | {mf1:.4f} | {lat} |\n", encoding="utf-8")
print(md)
PY
echo "[PATHS]"; echo "  LAST_DIR = $(cd "$LAST"&&pwd)"; echo "  RESULT   = $(cd "$LAST"&&pwd)/$(basename "$RES")"; echo "  SUMMARY  = $(cd "$(dirname "$MD")"&&pwd)/$(basename "$MD")"
