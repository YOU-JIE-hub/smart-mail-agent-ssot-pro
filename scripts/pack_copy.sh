#!/usr/bin/env bash
set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"
OUT="release_staging/${TS}"; mkdir -p "$OUT"
# 檔案清單：排除大型與生成物
rsync -a --exclude ".git" --exclude ".venv" --exclude "node_modules" --exclude "reports_auto/logs" --exclude "models" --exclude "weights" --exclude "datasets" --exclude "data" ./ "$OUT/src/"
(cd "$OUT" && zip -q -r "../chatpack_${TS}.zip" "src")
echo "[pack] -> release_staging/chatpack_${TS}.zip"
