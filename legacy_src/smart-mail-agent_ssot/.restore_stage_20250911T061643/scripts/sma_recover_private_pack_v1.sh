#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"

TS="${TS:-$(ls -td release_staging/*/ | head -n1 | xargs -I{} basename {} || true)}"
PRIV_DIR="release_staging/${TS}/private"
PRIV_TAR="release_staging/private_bundle_${TS}.tar.gz"

RESTORE="restore_packs/${TS}"
mkdir -p "$RESTORE"

if [ -d "$PRIV_DIR" ]; then
  echo "[INFO] using dir $PRIV_DIR"
  rsync -a "$PRIV_DIR/" "$RESTORE/"
elif [ -f "$PRIV_TAR" ]; then
  echo "[INFO] extracting $PRIV_TAR"
  tar -C "$RESTORE" -xzf "$PRIV_TAR"
  mv "$RESTORE/private/"* "$RESTORE/" && rmdir "$RESTORE/private" || true
else
  echo "[FATAL] no private dir or tar found for $TS"; exit 2
fi

echo "[OK] restored under $RESTORE"
echo "[INFO] files:"
ls -lh "$RESTORE" | sed -n '1,200p'

if [ "${REHYDRATE:-0}" = "1" ]; then
  echo "[STEP] rehydrate into project layout and re-evaluate"
  mkdir -p data/intent_eval artifacts_prod reports_auto/kie_eval
  # intent
  [ -f "$RESTORE/dataset.cleaned.jsonl" ] && cp -f "$RESTORE/dataset.cleaned.jsonl" data/intent_eval/dataset.cleaned.jsonl
  [ -f "$RESTORE/dataset.cleaned.csv" ]   && cp -f "$RESTORE/dataset.cleaned.csv"   data/intent_eval/dataset.cleaned.csv
  [ -f "$RESTORE/dataset.jsonl" ]         && cp -f "$RESTORE/dataset.jsonl"         data/intent_eval/dataset.jsonl
  # kie
  [ -f "$RESTORE/gold_merged.jsonl" ]     && cp -f "$RESTORE/gold_merged.jsonl"     data/kie_eval/gold_merged.jsonl
  # spam
  [ -f "$RESTORE/text_predictions_test.tsv" ] && cp -f "$RESTORE/text_predictions_test.tsv" artifacts_prod/text_predictions_test.tsv

  # re-run full evaluation
  bash scripts/sma_oneclick_eval_all_pro.sh
  echo "[DONE] re-evaluation finished."
else
  echo "[HINT] 僅復原；若要覆寫到專案並重跑：REHYDRATE=1 bash scripts/sma_recover_private_pack_v1.sh"
fi
