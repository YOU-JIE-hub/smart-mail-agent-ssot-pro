#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1090
source .sma_tools/env_guard.sh

moved=0
if [ -d artifacts_prod/artifacts_prod ]; then
  echo "[INFO] 偵測到重複巢狀 artifacts_prod，開始搬移到外層…"
  shopt -s dotglob
  mv -f artifacts_prod/artifacts_prod/* artifacts_prod/ 2>/dev/null || true
  rmdir artifacts_prod/artifacts_prod 2>/dev/null || true
  moved=1
fi

for f in artifacts_prod/model_pipeline.pkl artifacts_prod/ens_thresholds.json artifacts_prod/intent_rules_calib_v11c.json; do
  if [ -f "$f" ]; then
    sha=$(sha256sum "$f" | awk '{print $1}')
    echo "[OK] $f 存在 sha256=$sha"
  else
    echo "[WARN] 缺少關鍵工件：$f"
  fi
done

if [ "$moved" -eq 1 ]; then
  echo "[INFO] artifacts_prod 搬移完成"
fi

exit 0
