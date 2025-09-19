#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
ts(){ date +%Y%m%d-%H%M; }
STAMP="$(ts)"
OUTDIR="artifacts_release/min_triplet_${STAMP}"
mkdir -p "$OUTDIR" "artifacts_release" "reports_auto"

# INTENT
mkdir -p "$OUTDIR/intent"
cp -f artifacts/intent_pro_cal.pkl "$OUTDIR/intent/" 2>/dev/null || true
cp -f reports_auto/intent_thresholds.json "$OUTDIR/intent/" 2>/dev/null || true
if [[ -f .sma_tools/runtime_threshold_router.py ]]; then
  cp -f .sma_tools/runtime_threshold_router.py "$OUTDIR/intent/"
fi

# SPAM
mkdir -p "$OUTDIR/spam"
cp -f artifacts_prod/model_pipeline.pkl "$OUTDIR/spam/" 2>/dev/null || true
cp -f artifacts_prod/ens_thresholds.json "$OUTDIR/spam/" 2>/dev/null || true

# KIE (有完整權重就一起放，否則只放 tokenizer/config)
mkdir -p "$OUTDIR/kie"
if [[ -d artifacts/releases/kie_xlmr/current ]]; then
  cp -rf artifacts/releases/kie_xlmr/current "$OUTDIR/kie/"
fi

# README & ZIP
cat > "$OUTDIR/README_MIN_TRIPLET.md" <<'MD'
Minimal Triplet:
- INTENT: intent_*.pkl + intent_thresholds.json (+ runtime_threshold_router.py)
- SPAM:   model_pipeline.pkl + ens_thresholds.json
- KIE:    artifacts/releases/kie_xlmr/current/ (config + tokenizer + model.safetensors)
MD
ZIP="reports_auto/min_triplet_bundle_${STAMP}.zip"
( cd "$OUTDIR" && zip -q -r "../$(basename "$ZIP")" . )
echo "[OK] bundle -> $ZIP"
