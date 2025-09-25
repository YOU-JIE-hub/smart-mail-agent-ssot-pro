#!/usr/bin/env bash
set -euo pipefail

PROJ_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 啟動 venv（若存在）
if [ -d "${PROJ_ROOT}/.venv" ]; then
  # shellcheck disable=SC1090
  source "${PROJ_ROOT}/.venv/bin/activate"
fi

export PYTHONNOUSERSITE=1
export PYTHONUNBUFFERED=1
export PYTHONPATH="${PROJ_ROOT}/src:${PROJ_ROOT}:${PROJ_ROOT}/scripts:${PROJ_ROOT}/.sma_tools:${PYTHONPATH:-}"

export SMA_DB_PATH="${SMA_DB_PATH:-db/sma.sqlite}"
export SMA_DB_URL="${SMA_DB_URL:-sqlite:///db/sma.sqlite}"

export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-}"
export SMTP_HOST="${SMTP_HOST:-}"
export SMTP_PORT="${SMTP_PORT:-}"
export SMTP_USER="${SMTP_USER:-}"
export SMTP_PASS="${SMTP_PASS:-}"
export SMTP_SENDER="${SMTP_SENDER:-}"
export SMA_OUTBOX_DIR="${SMA_OUTBOX_DIR:-rpa_out/email_outbox}"

mkdir -p "${PROJ_ROOT}/reports_auto/logs" "${PROJ_ROOT}/reports_auto/status" \
         "${PROJ_ROOT}/rpa_out/email_outbox" "${PROJ_ROOT}/rpa_out/tickets" \
         "${PROJ_ROOT}/rpa_out/diffs" "${PROJ_ROOT}/rpa_out/faq_replies" \
         "${PROJ_ROOT}/rpa_out/quotes" "${PROJ_ROOT}/legacy" \
         "$(dirname "${SMA_DB_PATH}")"
