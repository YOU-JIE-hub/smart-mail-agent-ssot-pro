#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="reports_auto/e2e_mail"
LATEST="$ROOT/LATEST"

# 自癒：若 LATEST 無效就重建
if [[ ! -d "$LATEST" ]]; then
  CAND="$(ls -1dt "$ROOT"/* 2>/dev/null | grep -v '/LATEST$' | head -n1 || true)"
  if [[ -n "$CAND" ]]; then ln -sfn "$(readlink -f "$CAND")" "$LATEST"; fi
fi

echo "[LATEST] $(readlink -f "$LATEST" || echo "$LATEST")"

if [[ -d "$LATEST" ]]; then
  # 關鍵：-L 讓 find 追蹤 symlink
  find -L "$LATEST" -maxdepth 2 -type f | sort
else
  echo "[INFO] 尚無 E2E 輸出。先跑：scripts/sma_e2e_oneclick_logged.sh"
fi
