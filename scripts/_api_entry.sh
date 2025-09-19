#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. scripts/env.default
# 把所有輸出落到指定檔案
exec python -u -m tools.api_server >>"reports_auto/api/20250917T050703/api.out" 2>>"reports_auto/api/20250917T050703/api.err"
