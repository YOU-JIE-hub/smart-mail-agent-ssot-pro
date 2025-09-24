#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/bundles"; mkdir -p "$OUT"

online="$(ls -1dt reports_auto/online/*/ 2>/dev/null | head -n1 || true)"
pro="$(ls -1dt reports_auto/pro/*/ 2>/dev/null | head -n1 || true)"
e2e="$(ls -1dt reports_auto/e2e/*/ 2>/dev/null | head -n1 || true)"

ZIP="$OUT/sma_evidence_${TS}.zip"
tmpdir="$(mktemp -d)"; trap 'rm -rf "$tmpdir"' EXIT
mkdir -p "$tmpdir/online" "$tmpdir/pro" "$tmpdir/e2e"

[ -n "$online" ] && cp -R "$online" "$tmpdir/online/latest"
[ -n "$pro"    ] && cp -R "$pro"    "$tmpdir/pro/latest"
[ -n "$e2e"    ] && cp -R "$e2e"    "$tmpdir/e2e/latest"

( cd "$tmpdir" && zip -qr "$ZIP" . )
sha256sum "$ZIP" | tee "$ZIP.SHA256SUMS"
echo "$ZIP"
