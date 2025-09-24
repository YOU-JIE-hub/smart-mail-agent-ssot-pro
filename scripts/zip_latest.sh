#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
OUT="$(readlink -f reports_auto/online/latest || true)"
[ -z "$OUT" ] && { echo "no latest"; exit 1; }
ZIP="${OUT##*/}.zip"
( cd "$(dirname "$OUT")" && zip -qr "$ZIP" "$(basename "$OUT")" )
echo "ZIP: $(dirname "$OUT")/$ZIP"
