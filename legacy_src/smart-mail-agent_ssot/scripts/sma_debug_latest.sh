#!/usr/bin/env bash
set -Eeuo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$BASE/reports_auto/e2e_mail"
LATEST="$ROOT/LATEST"
echo "[BASE] $BASE"
echo "[ROOT] $ROOT"
echo "[EXIST ROOT?] $( [[ -d "$ROOT" ]] && echo yes || echo no )"
echo "[EXIST LATEST?] $( [[ -e "$LATEST" ]] && echo yes || echo no )"
echo "[IS DIR LATEST?] $( [[ -d "$LATEST" ]] && echo yes || echo no )"
echo "[IS SYMLINK LATEST?] $( [[ -L "$LATEST" ]] && echo yes || echo no )"
if [[ -L "$LATEST" ]]; then
  echo "[READLINK] $(readlink "$LATEST")"
  echo "[RESOLVED] $(readlink -f "$LATEST" || true)"
fi
echo "[CAND PICKED] $("$BASE"/scripts/sma__pick_latest.sh || true)"
echo "[TREE]"
find "$ROOT" -maxdepth 2 -mindepth 1 -printf "%M %TY-%Tm-%Td %TH:%TM %p\n" | sort -r
