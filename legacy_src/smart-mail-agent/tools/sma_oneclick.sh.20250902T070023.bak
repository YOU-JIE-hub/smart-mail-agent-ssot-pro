#!/usr/bin/env bash
set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"; LOG_DIR="reports_auto/logs"; mkdir -p "$LOG_DIR"
RUN_LOG="$LOG_DIR/oneclick_run_${TS}.log"; ERR_LOG="$LOG_DIR/oneclick_error_${TS}.log"
on_err(){ ec=$?; { echo "----- ONECLICK ERROR @ $(date -Iseconds) -----"; echo "EXIT_CODE=$ec"; echo "LAST_CMD=${BASH_COMMAND}"; echo "PWD=$(pwd)"; echo "ENV SMA_SPAM_TARGET_RATE=${SMA_SPAM_TARGET_RATE:-unset}"; echo "ENV OFFLINE=${OFFLINE:-unset}"; tail -n 200 "$RUN_LOG" 2>/dev/null || true; } >> "$ERR_LOG"; echo "ERROR: one-click failed; see $ERR_LOG"; exit "$ec"; }
trap on_err ERR
. ".sma_tools/env_guard.sh" | tee -a "$RUN_LOG"
test -f artifacts_prod/model_pipeline.pkl || { echo "ERROR: missing artifacts_prod/model_pipeline.pkl" | tee -a "$RUN_LOG"; exit 3; }
test -f artifacts_prod/ens_thresholds.json || { echo "ERROR: missing artifacts_prod/ens_thresholds.json" | tee -a "$RUN_LOG"; exit 4; }
test -f artifacts/intent_pro_cal.pkl || { echo "ERROR: missing artifacts/intent_pro_cal.pkl" | tee -a "$RUN_LOG"; exit 5; }
(test -d kie || test -d reports_auto/kie/kie) || { echo "ERROR: missing KIE model dir" | tee -a "$RUN_LOG"; exit 6; }
EML_DIR="${SMA_EML_DIR:-data/demo_eml}"; export OFFLINE="${OFFLINE:-1}" SMA_SPAM_TARGET_RATE="${SMA_SPAM_TARGET_RATE:-0.38}" SMA_SPAM_DEBUG=1
echo "SMA PRINT OK :: ONECLICK START (EML_DIR=$EML_DIR)" | tee -a "$RUN_LOG"
./scripts/sma_e2e_mail.sh "$EML_DIR" 2>&1 | tee -a "$RUN_LOG"
python scripts/sma_spam_autocut.py 2>&1 | tee -a "$RUN_LOG"
./scripts/sma_e2e_mail.sh "$EML_DIR" 2>&1 | tee -a "$RUN_LOG"
python scripts/sma_verify_e2e.py 2>&1 | tee -a "$RUN_LOG"
python scripts/sma_release_pack.py 2>&1 | tee -a "$RUN_LOG"
echo "SMA PRINT OK :: ONECLICK DONE" | tee -a "$RUN_LOG"
