#!/usr/bin/env bash
set -Eeuo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$BASE/reports_auto/e2e_mail"
# 列出最新的真實 run 目錄
find "$ROOT" -mindepth 1 -maxdepth 1 -type d ! -name 'LATEST' -printf "%T@ %p\n" \
  | sort -nr | awk 'NR==1{for(i=2;i<=NF;i++){printf (i==2?"":" "); printf $i} print ""}'
