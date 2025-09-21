#!/usr/bin/env bash
# Enrich latest run's cases.jsonl with text, then reroute intents.
set -Eeuo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"

pick_run_dir() {
  base="$ROOT/reports_auto/e2e_mail"
  [ -d "$base" ] || { echo ""; return; }
  mapfile -t dirs < <(find "$base" -maxdepth 1 -type d -regex '.*/[0-9]{8}T[0-9]{6}$' -printf "%T@ %p\n" | sort -nr | awk '{print $2}')
  for d in "${dirs[@]}"; do
    [ -f "$d/cases.jsonl" ] && echo "$d" && return
  done
  echo ""
}

RUN_DIR="$(pick_run_dir || true)"
[ -z "${RUN_DIR:-}" ] && RUN_DIR="$ROOT/reports_auto/e2e_mail/20250902T144500"
[ -d "$RUN_DIR" ] || { echo "[FATAL] no usable e2e run dir"; exit 2; }

python scripts/sma_e2e_enrich_cases_text.py --run-dir "$RUN_DIR" || true
python scripts/sma_reroute_last_run_intent.py --run-dir "$RUN_DIR" || true

echo "[RESULT] run_dir=$RUN_DIR"
for f in TEXT_ENRICH_SUMMARY.md intent_reroute_summary.md intent_reroute_audit.csv intent_reroute_suggestion.ndjson; do
  if [ -f "$RUN_DIR/$f" ]; then
    echo "[OK] $f -> $RUN_DIR/$f"
  else
    echo "[MISS] $f"
  fi
done
