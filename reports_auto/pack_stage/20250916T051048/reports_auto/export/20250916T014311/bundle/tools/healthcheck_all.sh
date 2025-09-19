#!/usr/bin/env bash
set -Eeuo pipefail
cd "${ROOT:-$PWD}"

echo "[A] TRI"
python tools/tri_suite.py || true
LATEST=$(ls -t reports_auto/eval/*/tri_suite.json 2>/dev/null | head -n1 || true)
[ -n "$LATEST" ] && echo "TRI -> $LATEST"

echo "[B] KIE"
KIE_IN=""
for c in data/kie/test_real.jsonl data/kie/test.jsonl fixtures/eval_set.jsonl; do
  if [ -s "$c" ]; then KIE_IN="$c"; break; fi
done
if [ "$KIE_IN" = "fixtures/eval_set.jsonl" ]; then
  # 轉成 {"text": "..."} 給 eval 用
  python - <<'PYX' < fixtures/eval_set.jsonl > reports_auto/kie/_from_fixtures.jsonl
import sys, json
for ln in sys.stdin:
    o=json.loads(ln); e=o.get("email", {})
    text=(e.get("subject","") + "\n" + e.get("body","")).strip()
    print(json.dumps({"text": text}, ensure_ascii=False))
PYX
  KIE_IN="reports_auto/kie/_from_fixtures.jsonl"
fi
mkdir -p reports_auto/kie
python tools/kie/eval.py "$KIE_IN" "reports_auto/kie/pred.jsonl" || true

echo "[C] SPAM (摘要存在即可)"
[ -f reports_auto/prod_quick_report.md ] && sed -n '1,20p' reports_auto/prod_quick_report.md || echo "no spam report"
