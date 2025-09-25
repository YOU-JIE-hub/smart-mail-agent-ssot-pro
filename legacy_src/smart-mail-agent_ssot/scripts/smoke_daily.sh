#!/usr/bin/env bash
set -Eeuo pipefail
cd "${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"
TS="$(date +%Y%m%dT%H%M%S)"
python -m smart_mail_agent.cli.e2e --eml-dir tests/_data/eml \
  --out-root "reports_auto/e2e_mail/$TS" --db-path db/sma.sqlite \
  --ndjson "reports_auto/events/${TS}.ndjson" || true
RUN_DIR="reports_auto/e2e_mail/$TS"
# FAQ 內嵌（可由環境變數切換，預設開）
: "${SMA_USE_RAG_FAQ:=1}"
if [ "$SMA_USE_RAG_FAQ" = "1" ]; then
  python tools/enrich_outbox_with_faq.py --run-dir "$RUN_DIR" --kb-dir "kb/faq" --topk 3 --ndjson "reports_auto/events/${TS}.ndjson" || true
fi
# 門檻揭示追加
python tools/summary_thresholds_block.py --run-dir "$RUN_DIR" || true
# 送信（遵循 SMTP 模式與白名單；失敗會由 send_latest.sh 退避 outbox-only）
scripts/send_latest.sh || true
# KPI 彙總
python tools/events_rollup.py || true
echo "[SMOKE DONE] run=$RUN_DIR"
