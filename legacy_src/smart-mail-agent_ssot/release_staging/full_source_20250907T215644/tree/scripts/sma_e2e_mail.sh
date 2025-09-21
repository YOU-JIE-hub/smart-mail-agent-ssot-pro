#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
IN="${1:-data/demo_eml}"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/e2e_mail/${TS}"
LOG="reports_auto/logs"
DBDIR="db"
mkdir -p "${OUT}/rpa_out"/{email_outbox,tickets,diffs,faq_replies,quotes} "${LOG}" "${DBDIR}"

echo "[E2E] input=${IN}"
python scripts/e2e_mail_runner.py \
  --in "${IN}" \
  --out "${OUT}" \
  --db "${DBDIR}/sma.sqlite" \
  --pipeline-log "${LOG}/pipeline.ndjson"

echo "[E2E] done. summary => ${OUT}/SUMMARY.md"
