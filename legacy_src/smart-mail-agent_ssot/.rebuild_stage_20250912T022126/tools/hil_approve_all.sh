#!/usr/bin/env bash
set -Eeuo pipefail
RUN_DIR="${1:?usage: hil_approve_all.sh <RUN_DIR>}"
OUTBOX="$RUN_DIR/rpa_out/email_outbox"
BLOCKED="$RUN_DIR/rpa_out/email_blocked"
mkdir -p "$OUTBOX" "$BLOCKED"
# 移回被擋信
shopt -s nullglob
for f in "$BLOCKED"/*.txt; do mv -f "$f" "$OUTBOX/"; done
# 建立 .approved
for t in "$OUTBOX"/*.txt; do touch "${t%.txt}.approved"; done
echo "[OK] approved all in $OUTBOX"
