#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1090
source .sma_tools/env_guard.sh
bash scripts/sma_e2e_oneclick_logged.sh "${1:-data/demo_eml}"
