#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "用法：bash scripts/sma_unpack_chat_context_v1.sh chat_context_bundle_*.zip"
  exit 2
fi

ZIP="$1"
DEST="chat_context_imported"
mkdir -p "$DEST"
unzip -q "$ZIP" -d "$DEST"

# 抓到 private bundle 後可選擇一鍵復現
PRI_TAR="$(find "$DEST" -maxdepth 3 -name 'private_bundle_*.tar.gz' | head -n1 || true)"
if [ -n "$PRI_TAR" ]; then
  echo "[INFO] found private bundle: $PRI_TAR"
  echo "[HINT] 如要覆蓋到標準路徑並重跑評估："
  echo "      cp '$PRI_TAR' . && bash scripts/sma_recover_private_pack_v1.sh REHYDRATE=1 TS=$(basename "$PRI_TAR" | sed 's/private_bundle_//; s/.tar.gz//')"
else
  echo "[WARN] 未找到 private bundle，僅完成解包。"
fi

echo "[OK] 解包完成於 $DEST"
ls -lah "$DEST"
