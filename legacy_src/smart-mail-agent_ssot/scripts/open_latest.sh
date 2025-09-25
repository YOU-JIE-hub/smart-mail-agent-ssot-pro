#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
pick_latest() {
  find "$1" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-
}
TARGET="${1:-$ROOT/reports_auto/capture}"
[ -d "$TARGET" ] || { echo "[ERR] not found: $TARGET" >&2; exit 2; }
[ -d "$TARGET" ] && [ -z "${2:-}" ] && TARGET="$(pick_latest "$TARGET")"
echo "[PATH] $TARGET"
if command -v explorer.exe >/dev/null 2>&1; then
  explorer.exe "$(wslpath -w "$TARGET")" >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$TARGET" >/dev/null 2>&1 || true
fi
