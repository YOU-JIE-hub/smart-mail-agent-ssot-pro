#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
IN_INTENT="${1:-$ROOT/artifacts_inbox/intent}"
IN_SPAM="${2:-$ROOT/artifacts_inbox/spam}"
IN_KIE="${3:-$ROOT/artifacts_inbox/kie}"
log(){ printf '[%s] %s\n' "$(date +%F' '%T)" "$*"; }

cd "$ROOT"

# 0) 清掉 Windows 的 Zone.Identifier 殘檔
log "cleanup Zone.Identifier"
find "$IN_INTENT" "$IN_SPAM" "$IN_KIE" -type f -name '*:Zone.Identifier' -delete 2>/dev/null || true

# 1) INTENT ------------------------------------------------------------
log "ingest INTENT"
mkdir -p artifacts reports_auto .sma_tools
cp -f "$IN_INTENT/artifacts/intent_pro_cal.pkl" artifacts/ 2>/dev/null || { echo "[WARN] intent_pro_cal.pkl 不在 $IN_INTENT/artifacts/"; }
cp -f "$IN_INTENT/reports_auto/intent_thresholds.json" reports_auto/ 2>/dev/null || { echo "[WARN] intent_thresholds.json 不在 $IN_INTENT/reports_auto/"; }
# 推論/工具腳本（可選）
for f in runtime_threshold_router.py train_pro_fresh.py tune_thresholds.py eval_with_threshold.py; do
  [[ -f "$IN_INTENT/.sma_tools/$f" ]] && cp -f "$IN_INTENT/.sma_tools/$f" .sma_tools/ || true
done
# 驗收集（可選）
mkdir -p data/intent
[[ -f "$IN_INTENT/data/intent/external_realistic_test.clean.jsonl" ]] && \
  cp -f "$IN_INTENT/data/intent/external_realistic_test.clean.jsonl" data/intent/ || true

# 2) SPAM --------------------------------------------------------------
log "ingest SPAM"
mkdir -p artifacts_prod scripts
cp -f "$IN_SPAM/artifacts_prod/model_pipeline.pkl" artifacts_prod/ 2>/dev/null || { echo "[WARN] model_pipeline.pkl 不在 $IN_SPAM/artifacts_prod/"; }
cp -f "$IN_SPAM/artifacts_prod/ens_thresholds.json" artifacts_prod/ 2>/dev/null || { echo "[WARN] ens_thresholds.json 不在 $IN_SPAM/artifacts_prod/"; }
# 評測/推論腳本（可選）
for f in sma_quick_eval.py sma_infer_eml.py _sma_common.py model_doctor.py; do
  [[ -f "$IN_SPAM/scripts/$f" ]] && cp -f "$IN_SPAM/scripts/$f" scripts/ || true
done
# 報表（可選，便於對照）
mkdir -p reports_auto/archive/spam_src
[[ -d "$IN_SPAM/reports_auto" ]] && cp -rf "$IN_SPAM/reports_auto/." reports_auto/archive/spam_src/ || true

# 3) KIE ---------------------------------------------------------------
log "ingest KIE"
# 目標放到 HuggingFace 標準結構下，並設 current 指向
OUT_KIE="$ROOT/artifacts/releases/kie_xlmr/$(date +%Y%m%dT%H%M%SZ)-kie_xlmr"
mkdir -p "$OUT_KIE"
if [[ -d "$IN_KIE/kie" ]]; then
  cp -rf "$IN_KIE/kie/." "$OUT_KIE/"
  ln -sfn "$OUT_KIE" "$ROOT/artifacts/releases/kie_xlmr/current"
  # 保留你的 RUNME 檔供使用者 demo
  mkdir -p "$ROOT/reports_auto/archive/kie_src"
  for f in RUNME_kie.sh RUNME_kie_eval.py RUNME_kie_demo.py; do
    [[ -f "$IN_KIE/$f" ]] && cp -f "$IN_KIE/$f" "$ROOT/reports_auto/archive/kie_src/" || true
  done
else
  echo "[WARN] $IN_KIE/kie 不存在，略過 KIE"
fi

# 4) 摘要 --------------------------------------------------------------
echo "=== INSTALLED MINIMAL WEIGHTS ==="
[[ -f artifacts/intent_pro_cal.pkl ]] && echo "INTENT -> artifacts/intent_pro_cal.pkl"
[[ -f reports_auto/intent_thresholds.json ]] && echo "INTENT thr -> reports_auto/intent_thresholds.json"
[[ -f artifacts_prod/model_pipeline.pkl ]] && echo "SPAM   -> artifacts_prod/model_pipeline.pkl"
[[ -f artifacts_prod/ens_thresholds.json ]] && echo "SPAM thr -> artifacts_prod/ens_thresholds.json"
[[ -d artifacts/releases/kie_xlmr/current ]] && echo "KIE    -> artifacts/releases/kie_xlmr/current (含 model.safetensors)"

echo "[OK] ingest done."
