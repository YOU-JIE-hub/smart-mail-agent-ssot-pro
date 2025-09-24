#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
OUT="$(ls -1dt reports_auto/online/*/ 2>/dev/null | head -n1)"
[ -z "$OUT" ] && { echo "OUT:<none> 先跑：make -f scripts/Makefile.repro.mk probe"; exit 0; }
echo "OUT: $OUT"
for x in readyz debug_models intent spam kie; do printf "%-14s %s\n" "$x" "$(cat "$OUT/$x.code" 2>/dev/null || echo NA)"; done
echo "--- intent.body (pretty) ---"
python - <<PY "$OUT/intent.body" 2>/dev/null || sed -n "1,120p" "$OUT/intent.body" || echo "<missing>"
import sys,json
try:
  d=json.load(open(sys.argv[1],encoding="utf-8"))
  keep={"task":d.get("task"),"label":d.get("label"),"score":d.get("score"),
        "meta":{"path":d.get("meta",{}).get("path"),"classes_":d.get("meta",{}).get("classes_",[])}}
  print(json.dumps(keep,ensure_ascii=False,indent=2))
except Exception as e:
  print(f"<parse-failed: {type(e).__name__}: {e}>")
PY
[ -s "$OUT/uvicorn.err" ] && { echo "--- tail uvicorn.err ---"; tail -n 80 "$OUT/uvicorn.err"; } || echo "<no uvicorn.err>"
[ -s "$OUT/run.log" ]     && { echo "--- tail run.log ---"; tail -n 80 "$OUT/run.log"; }   || echo "<no run.log>"
