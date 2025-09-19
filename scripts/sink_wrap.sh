#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="/home/youjie/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
ERR_DIR="$ROOT/reports_auto/ERR"; mkdir -p "$ERR_DIR"
SERVER_LOG="$ERR_DIR/server.log"; RUN_LOG="$ERR_DIR/run.log"; API_ERR="$ERR_DIR/api.err"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$RUN_LOG"; }
on_err(){ ec=$?; echo "[ERR] cmd:'$BASH_COMMAND' ec=$ec" | tee -a "$RUN_LOG"; echo "$BASH_COMMAND" >> "$API_ERR"; exit $ec; }
trap on_err ERR
"$@" >>"$SERVER_LOG" 2>>"$API_ERR"
