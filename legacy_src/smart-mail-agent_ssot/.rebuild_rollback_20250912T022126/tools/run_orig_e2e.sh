#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
. scripts/lib/guard.sh; guard::at_root
bash scripts/sma_e2e_all.sh
