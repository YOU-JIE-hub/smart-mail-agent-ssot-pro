#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
. scripts/lib/guard.sh; guard::at_root
. scripts/lib/bootstrap_db.sh || true
bash scripts/ops_quickcheck.sh
