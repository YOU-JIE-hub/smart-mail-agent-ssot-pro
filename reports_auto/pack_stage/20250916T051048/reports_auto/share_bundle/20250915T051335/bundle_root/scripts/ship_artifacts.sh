#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${SMA_ROOT:-$PWD}"
cd "$ROOT"
mkdir -p reports_auto/artifacts
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/artifacts/sma_bundle_${TS}.tar.gz"
tar -czf "$OUT" reports_auto/audit.sqlite3 reports_auto/logs reports_auto/status 2>/dev/null || true
echo "$OUT"
