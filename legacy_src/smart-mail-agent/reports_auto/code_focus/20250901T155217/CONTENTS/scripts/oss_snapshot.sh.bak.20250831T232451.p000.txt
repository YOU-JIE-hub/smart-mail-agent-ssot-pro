#!/usr/bin/env bash
set -Eeuo pipefail
TS="$(date +%Y%m%dT%H%M%S)"
mkdir -p share reports
# 清單
{ echo "=== tree (top2) ==="; find . -maxdepth 2 -mindepth 1 \
   -not -path "./.git*" -not -path "./.venv*" -not -path "./htmlcov*" -print | sort; } > "share/repo_tree_${TS}.txt"
# 淨化打包（不含 venv/.git/cache/輸出）
tar --sort=name -czf "share/oss_snapshot_${TS}.tar.gz" \
  --exclude-vcs --exclude=".venv" --exclude="htmlcov" \
  --exclude="reports" --exclude="share" --exclude=".pytest_cache" --exclude=".ruff_cache" \
  --exclude="data/output" --exclude="data/tmp" \
  .
echo "SNAPSHOT=share/oss_snapshot_${TS}.tar.gz"
echo "TREE=share/repo_tree_${TS}.txt"
