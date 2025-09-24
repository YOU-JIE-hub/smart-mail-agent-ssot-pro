#!/usr/bin/env bash
set -Eeuo pipefail; umask 022

# 先試 symlink，再回退到最新時間戳資料夾
OUT=""
if [ -e reports_auto/online/latest ]; then
  OUT="$(readlink -f reports_auto/online/latest 2>/dev/null || echo)"
fi
if [ -z "$OUT" ] || [ ! -d "$OUT" ]; then
  OUT="$(ls -1dt reports_auto/online/* 2>/dev/null | head -n1 || true)"
fi

if [ -z "$OUT" ] || [ ! -d "$OUT" ]; then
  echo "OUT: <none>"
  echo "沒有找到任何 online 證據資料夾。先跑：make -f scripts/Makefile.repro.mk probe"
  exit 0
fi

echo "OUT: $OUT"
for x in readyz debug_models intent spam kie; do
  f="$OUT/$x.code"; printf "%-14s %s\n" "$x" "$( [ -s "$f" ] && cat "$f" || echo NA )"
done

echo "--- intent.body ---"
if [ -s "$OUT/intent.body" ]; then
  if command -v jq >/dev/null 2>&1; then
    jq '{task, label, score, meta:{path,classes_}}' "$OUT/intent.body" 2>/dev/null \
      || sed -n '1,120p' "$OUT/intent.body" || echo "<empty>"
  else
    python - <<'PY' "$OUT/intent.body" 2>/dev/null || sed -n '1,120p' "$OUT/intent.body" || echo "<empty>"
import json,sys
try:
    d=json.load(open(sys.argv[1],encoding='utf-8'))
    o={"task":d.get("task"),"label":d.get("label"),"score":d.get("score"),
       "meta":{"path":d.get("meta",{}).get("path"),"classes_":d.get("meta",{}).get("classes_",[])}} 
    print(json.dumps(o,ensure_ascii=False,indent=2))
except Exception as e:
    print(f"<parse-failed: {type(e).__name__}: {e}>")
PY
  fi
else
  echo "<intent.body not found>"
fi

# 補一些常見證據尾段
for f in run.log uvicorn.out uvicorn.err; do
  [ -s "$OUT/$f" ] && { echo "--- tail $f ---"; tail -n 60 "$OUT/$f"; }
done
