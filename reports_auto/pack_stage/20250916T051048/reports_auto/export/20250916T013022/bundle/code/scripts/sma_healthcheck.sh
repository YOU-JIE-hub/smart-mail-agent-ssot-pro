#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"; RUN="reports_auto/health/${TS}"
LOG="$RUN/run.log"; ERR="$RUN/health.err"
mkdir -p "$RUN" reports_auto/status reports_auto/.quarantine
exec > >(tee -a "$LOG") 2>&1
mapfile -t RUNDIRS < <(find reports_auto -maxdepth 3 -type d -regex '.*/[0-9]{8}T[0-9]{6}$' | sort || true)
if [ "${#RUNDIRS[@]}" -eq 0 ]; then
  ln -sfn "$RUN" reports_auto/LATEST || true
  echo "[WARN] no timestamped run dirs yet" | tee "reports_auto/status/HEALTH_${TS}.md"
  exit 0
fi
LAST="${RUNDIRS[${#RUNDIRS[@]}-1]}"; ln -sfn "$LAST" reports_auto/LATEST || true
namesN=""; seedsN=""; sentN=""
[ -f "$LAST/names.txt" ] && namesN="$(wc -l < "$LAST/names.txt" | tr -d ' ')"
[ -f "$LAST/seeds.jsonl" ] && seedsN="$(wc -l < "$LAST/seeds.jsonl" | tr -d ' ')"
OUTBOX="${SMA_OUTBOX_DIR:-rpa_out/email_outbox}"; [ -d "$OUTBOX" ] && sentN="$(find "$OUTBOX" -maxdepth 1 -type f | wc -l | tr -d ' ')"
echo "names=${namesN:-MISSING} seeds=${seedsN:-MISSING} sent=${sentN:-MISSING}" | tee "$RUN/nss.txt"
if [ -n "$namesN" ] && [ "$namesN" = "$seedsN" ] && [ "$seedsN" = "$sentN" ]; then
  echo "[OK] names==seeds==sent==$namesN" | tee "reports_auto/status/HEALTH_${TS}.md"
else
  echo "[FAIL] mismatch or missing → $(cd "$RUN"&&pwd)/nss.txt" | tee "reports_auto/status/HEALTH_${TS}.md"; exit 2
fi
