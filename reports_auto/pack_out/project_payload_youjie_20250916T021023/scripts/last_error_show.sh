#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/youjie/projects/smart-mail-agent-ssot-pro
P="reports_auto/LAST_ERROR_POINTERS.txt"
if [ -f "$P" ]; then
  echo "[LAST ERROR POINTERS]"; cat "$P"
  D="$(grep '^RUN_DIR=' "$P" | sed 's/^RUN_DIR=//')"
  command -v explorer.exe >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$D")" >/dev/null 2>&1 || true
else
  echo "[WARN] 尚無錯誤指標；看 LATEST：$(ls -ld reports_auto/LATEST 2>/dev/null || true)"
fi
