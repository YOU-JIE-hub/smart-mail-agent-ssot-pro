#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo -e "\033[31m[FATAL]\033[0m 專案不存在：$ROOT"; exit 2; }
. .venv/bin/activate 2>/dev/null || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:.sma_tools:${PYTHONPATH:-}"
mkdir -p reports_auto/logs
LOG="reports_auto/logs/$(date +%Y%m%d_%H%M%S)_oneclick_kie_full_v2.log"
ln -sf "$(basename "$LOG")" reports_auto/logs/latest.log
exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1
PS4='+ [\t] '; set -x
trap 'c=$?; echo -e "\n\033[31m[ERROR]\033[0m exit=$c line=$LINENO cmd=${BASH_COMMAND}"; echo "---- LOG TAIL ----"; tail -n 120 "$LOG" || true; exit $c' ERR

echo "[INFO] PWD=$PWD"; python -V; pip -V; echo
IN="data/intent/external_realistic_test.clean.jsonl"
PRED="reports_auto/predict_all.jsonl"
test -f "$IN" || { echo "[FATAL] 缺 $IN"; exit 3; }
test -f .sma_tools/sma_infer_all_three.py || { echo "[FATAL] 缺 .sma_tools/sma_infer_all_three.py"; exit 3; }

echo "[STEP] all_three → $PRED"
rm -f "$PRED"
PYTHONPATH="src:.sma_tools" python .sma_tools/sma_infer_all_three.py "$IN" --out "$PRED"

echo "[STEP] normalize(before KIE)…"
python .sma_tools/jsonl_doctor.py normalize -i "$PRED" -o "$PRED.tmp"
mv -f "$PRED.tmp" "$PRED"
python .sma_tools/jsonl_doctor.py validate -i "$PRED" || true

if [[ -f artifacts_kie/model/model.safetensors && -f .sma_tools/sma_kie_add.py ]]; then
  echo "[STEP] KIE merge via clean temp…"
  cp -f "$PRED" "$PRED.kie_in"
  PYTHONPATH="src:.sma_tools" python .sma_tools/sma_kie_add.py \
    --src "$IN" --pred_in "$PRED.kie_in" --pred_out "$PRED" \
    --kie_dir artifacts_kie/model --chunk 4 --maxlen 512 \
    --min_prob 0.30 --keep_labels amount,env,sla,date_time
  echo "[STEP] normalize(after KIE)…"
  python .sma_tools/jsonl_doctor.py normalize -i "$PRED" -o "$PRED.tmp"
  mv -f "$PRED.tmp" "$PRED"
  python .sma_tools/jsonl_doctor.py validate -i "$PRED" || true
else
  echo "[WARN] 無 KIE 權重或缺 sma_kie_add.py，跳過併入"
fi

echo "[STEP] regex fill（only for empty spans）…"
python .sma_tools/kie_regex_fill.py --src "$IN" --pred_in "$PRED" --pred_out "$PRED"

echo "[STEP] 摘要 …"
python - <<'PY'
import json,collections
cnt=collections.Counter(); n=0; empty=0
with open("reports_auto/predict_all.jsonl","r",encoding="utf-8") as f:
    for ln in f:
        if not ln.strip(): continue
        o=json.loads(ln); n+=1
        sp=(o.get("kie") or {}).get("spans",[])
        if not sp: empty+=1
        for s in sp: cnt[s.get("label","_")]+=1
print("[ROWS]", n, "| [EMPTY spans]", empty, "| [LABEL COUNTS]", dict(cnt))
PY

echo "[DONE] → reports_auto/predict_all.jsonl"
echo "[LOG ] 實時輸出：reports_auto/logs/latest.log（tail -f 可持續查看）"
