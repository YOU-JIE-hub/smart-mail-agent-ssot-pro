#!/usr/bin/env bash
set -Eeuo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$BASE/reports_auto/e2e_mail"
LATEST="$ROOT/LATEST"

# 若 LATEST 為壞連結或不存在，重建
if [[ -L "$LATEST" && ! -e "$LATEST" ]] || [[ ! -d "$LATEST" ]]; then
  CAND="$("$BASE"/scripts/sma__pick_latest.sh || true)"
  if [[ -n "$CAND" && -d "$CAND" ]]; then
    ln -sfn "$(readlink -f "$CAND")" "$LATEST"
  fi
fi

if [[ -d "$LATEST" ]]; then
  FILE="$LATEST/SUMMARY.md"
  echo "[LATEST] $LATEST"
  if [[ -f "$FILE" ]]; then
    ${PAGER:-cat} "$FILE"
    exit 0
  else
    echo "[INFO] 找不到 SUMMARY.md：$FILE"
    exit 2
  fi
else
  echo "[INFO] 尚無 E2E 輸出。先跑：scripts/sma_e2e_oneclick_logged.sh"
  exit 3
fi
