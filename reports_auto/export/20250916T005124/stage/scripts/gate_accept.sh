#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
set -a; . scripts/env.default 2>/dev/null || true; set +a
INTENT_JSON="$(ls -1dt reports_auto/eval_fix/2*/tri_results_fixed.json 2>/dev/null | head -n1 || true)"
KIE_JSON="$(ls -1dt reports_auto/kie_eval/2*/report.json 2>/dev/null | head -n1 || true)"
SPAM_JSON="$(ls -1dt reports_auto/spam_eval/2*/report.json 2>/dev/null | head -n1 || true)"

get_macro_f1(){ python - "$1" <<'PY'
import sys,json
p=sys.argv[1]
try:
  J=json.load(open(p,encoding="utf-8"))
  print(J.get("report",{}).get("macro avg",{}).get("f1-score",0.0))
except: print(0.0)
PY
}
get_acc(){ python - "$1" <<'PY'
import sys,json
p=sys.argv[1]
try:
  J=json.load(open(p,encoding="utf-8"))
  print(J.get("accuracy",0.0))
except: print(0.0)
PY
}
get_kie_f1(){ python - "$1" <<'PY'
import sys,json
p=sys.argv[1]
try:
  J=json.load(open(p,encoding="utf-8"))
  print(J.get("macro_presence_F1",0.0))
except: print(0.0)
PY
}

INTENT_F1="$( [ -f "$INTENT_JSON" ] && get_macro_f1 "$INTENT_JSON" || echo 0 )"
KIE_F1="$(    [ -f "$KIE_JSON" ]    && get_kie_f1    "$KIE_JSON"    || echo 0 )"
SPAM_ACC="$(  [ -f "$SPAM_JSON" ]  && get_acc       "$SPAM_JSON"   || echo 0 )"

echo "[GATE] intent macro-F1=$INTENT_F1 (>= ${SMA_INTENT_MIN_F1:-0.95})"
echo "[GATE] KIE    macro-F1=$KIE_F1    (>= ${SMA_KIE_MIN_F1:-0.90})"
echo "[GATE] spam   accuracy=$SPAM_ACC  (>= ${SMA_SPAM_MIN_F1:-0.98})"

FAIL=0
awk -v a="$INTENT_F1" -v t="${SMA_INTENT_MIN_F1:-0.95}" 'BEGIN{if(a+0<t+0) exit 1}'; FAIL=$((FAIL||$?))
# KIE/Spam 若無資料，report 會標記 SKIPPED；此時不擋版，但會警告
if [ -f "$KIE_JSON" ] && ! grep -q '"status":"SKIPPED"' "$KIE_JSON"; then
  awk -v a="$KIE_F1" -v t="${SMA_KIE_MIN_F1:-0.90}" 'BEGIN{if(a+0<t+0) exit 1}'; FAIL=$((FAIL||$?))
else
  echo "[WARN] KIE dataset missing -> gate skipped"
fi
if [ -f "$SPAM_JSON" ] && ! grep -q '"status":"SMOKE"' "$SPAM_JSON"; then
  awk -v a="$SPAM_ACC" -v t="${SMA_SPAM_MIN_F1:-0.98}" 'BEGIN{if(a+0<t+0) exit 1}'; FAIL=$((FAIL||$?))
else
  echo "[WARN] Spam dataset missing -> gate skipped (smoke only)"
fi

if [ "$FAIL" -ne 0 ]; then
  echo "[GATE][FAIL] 不達門檻"; exit 1
else
  echo "[GATE][PASS] 全部達標或允許跳過的項目缺資料"
fi
