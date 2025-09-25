#!/usr/bin/env bash
set -Eeuo pipefail
trap 'ec=$?; echo "[ERR] line:$LINENO cmd:${BASH_COMMAND} (exit=$ec)" >&2' ERR
ROOT="${SMA_ROOT:-$PWD}"; cd "$ROOT"
bash sma_phase9_6a_hotfix_guarded_migration.sh
SMA_STRICT=1 bash sma_phase9_5_closeout_assert_zero.sh
