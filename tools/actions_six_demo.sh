#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace; umask 022
cd ~/projects/smart-mail-agent-ssot-pro || { echo "[FATAL] repo not found"; exit 2; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
TS="$(date +%Y%m%dT%H%M%S)"
BUNDLEDIR="reports_auto/bundles"; mkdir -p "$BUNDLEDIR"
run(){ echo "== $1 =="; bash tools/action_one.sh "$1" "demo_${1}" || true; }
run make_quote_pdf
run create_ticket
run escalation_suggestion
run faq_reply_draft
run crm_update
run human_handoff
echo; echo "---- SUMMARY ----"
sed -n '1,80p' reports_auto/actions/latest/actions_summary.md || true
ZIP="$BUNDLEDIR/actions_six_${TS}.zip"
zip -qr "$ZIP" reports_auto/actions/latest || true
( cd "$BUNDLEDIR" && sha256sum "$(basename "$ZIP")" > "SHA256SUMS_${TS}_six" ) || true
echo "[OK] bundle -> $ZIP"
