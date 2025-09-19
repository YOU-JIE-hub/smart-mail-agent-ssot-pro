#!/usr/bin/env bash
set -Eeuo pipefail
echo "[restore] scan placeholders ... (OK if none)"
grep -RIl --include="*.placeholder" "." || true
