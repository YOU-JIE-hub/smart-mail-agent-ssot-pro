#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -x "$ROOT/scripts/obs/online_probe.sh" ]; then exec "$ROOT/scripts/obs/online_probe.sh" "$@"; fi
if [ -x "$ROOT/online_probe.sh" ]; then exec "$ROOT/online_probe.sh" "$@"; fi
echo "[FATAL] online_probe.sh not found in scripts/obs or repo root" >&2; exit 127
