#!/usr/bin/env bash
# log_guard.sh — 無論成功或閃退，統一把輸出寫檔；失敗另存 crash.json
set -Eeuo pipefail
set -o errtrace

_ts(){ date +%Y%m%dT%H%M%S; }

# 解析日誌根：優先 repo 的 reports_auto/logs，失敗就退到 /tmp/sma_logs
_resolve_logroot(){
  if [[ -n "${SMA_ROOT:-}" && -d "$SMA_ROOT/.git" ]]; then echo "$SMA_ROOT/reports_auto/logs"; return; fi
  if git rev-parse --show-toplevel &>/dev/null; then echo "$(git rev-parse --show-toplevel)/reports_auto/logs"; return; fi
  [[ -d "./reports_auto" ]] && { echo "./reports_auto/logs"; return; }
  echo "/tmp/sma_logs"
}

LOG_ROOT="$(_resolve_logroot)"
STAMP="$(_ts)"
LOG_DIR="${LOG_DIR:-$LOG_ROOT/$STAMP}"
mkdir -p "$LOG_DIR" || true
LOG_FILE="${LOG_FILE:-$LOG_DIR/run.log}"
CRASH_FILE="${CRASH_FILE:-$LOG_DIR/crash.json}"

# 將 stdout/stderr 同步寫檔（無 tee 時退回重導）
if command -v tee >/dev/null 2>&1; then
  exec > >(tee -a "$LOG_FILE") 2>&1
else
  exec >>"$LOG_FILE" 2>&1
fi

# 基本抬頭
echo "=== LOG BEGIN $(date -Iseconds) ==="
echo "[HOST] $(uname -a || echo n/a)"
python -V 2>/dev/null || true
echo "[WD]   $PWD"
echo "[ENV]  OFFLINE=${OFFLINE:-unset}  PYTHONPATH=${PYTHONPATH:-unset}"

# 記錄每次失敗的指令
_last_cmd=""
trap '_last_cmd=${BASH_COMMAND}' DEBUG

# 退出時，如 rc!=0 產生 crash.json
trap 'rc=$?; if [[ $rc -ne 0 ]]; then
  printf "{\n  \"ts\":\"%s\",\n  \"rc\":%d,\n  \"last_cmd\":%s,\n  \"log_file\":%s,\n  \"pwd\":%s\n}\n" \
    "$(date -Iseconds)" "$rc" \
    "$(printf "%q" "$_last_cmd")" \
    "$(printf "%q" "$LOG_FILE")" \
    "$(printf "%q" "$PWD")" > "$CRASH_FILE";
  echo "[CRASH] rc=$rc  crash.json => $CRASH_FILE"
else
  echo "=== LOG END   $(date -Iseconds) rc=0 ==="
fi' EXIT

# 對外暴露最後日誌位置（給包裝器/使用者）
export SMA_LAST_LOG="$LOG_FILE"
export SMA_LAST_LOG_DIR="$LOG_DIR"
