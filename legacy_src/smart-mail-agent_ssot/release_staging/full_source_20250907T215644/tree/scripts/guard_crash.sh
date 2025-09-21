#!/usr/bin/env bash
# guard_crash.sh — 最小穩定版（錯誤即落檔 + 指標檔）
set -Eeuo pipefail

RUN_MODE=0
if [[ "${1:-}" == "--run" ]]; then RUN_MODE=1; shift; fi
PHASE="${1:-GENERIC}"; shift || true

ROOT="${SMA_ROOT:-$PWD}"
cd "$ROOT" 2>/dev/null || true

TS="$(date +%Y%m%dT%H%M%S)"
mkdir -p reports_auto/{logs,status} 2>/dev/null || true
LOG="reports_auto/logs/${PHASE}_${TS}.log"
CRASH="reports_auto/logs/CRASH_${PHASE}_${TS}.log"
CRASH_MD="reports_auto/status/${PHASE}_CRASH_${TS}.md"
LAST_PTR="reports_auto/logs/LAST_CRASH_PATH.txt"

_redact_env() {
  env | sed -E 's/((^|_)(PASS|TOKEN|SECRET|KEY|COOKIE)(S)?=)[^=]*/\1***REDACTED***/Ig'
}

write_crash() {
  local ec="$1" cmd="$2" ln="$3" src="$4"
  {
    echo "# CRASH REPORT"
    echo
    echo "## WHEN"; date -u +"%Y-%m-%dT%H:%M:%SZ"; echo
    echo "## PHASE"; echo "$PHASE"; echo
    echo "## SHELL ERROR"; echo "exit_code=$ec"; echo "file=${src}"; echo "line=${ln}"; echo "last_command=${cmd}"; echo
    echo "## ENV (redacted)"; _redact_env; echo
    echo "## LOG TAIL (last 200 lines)"; echo "--- $LOG ---"
    tail -n 200 "$LOG" 2>/dev/null || echo "(log not available)"
  } > "$CRASH" || true

  {
    echo "# ${PHASE} Crash @ ${TS}"
    echo
    echo "- file: \`${CRASH}\`"
    echo "- exit_code: ${ec}"
    echo "- last_command: \`${cmd}\`"
    echo
    echo "原始日誌尾部請見上方檔案。"
  } > "$CRASH_MD" || true

  echo "$CRASH" > "$LAST_PTR" 2>/dev/null || true
  >&2 echo "[CRASH] saved: $CRASH"
}

on_err() {
  local ec=$?
  local ln="${BASH_LINENO[0]:-?}"
  local src="${BASH_SOURCE[1]:-<subshell>}"
  local cmd="${BASH_COMMAND:-<unknown>}"
  write_crash "$ec" "$cmd" "$ln" "$src"
  exit "$ec"
}

# 提供被 source 的模式
guard_enable() { trap on_err ERR; }

if [[ "$RUN_MODE" -eq 1 ]]; then
  # 導流到 LOG + 終端
  if command -v stdbuf >/dev/null 2>&1; then
    exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1
  else
    exec > >(tee -a "$LOG") 2>&1
  fi
  trap on_err ERR

  echo "=== [ENV] ==="
  echo "ROOT=$ROOT"
  echo "PHASE=$PHASE"
  python -V 2>/dev/null || true
  echo

  # **關鍵修補**：若使用者給了可選的「--」，在執行前把它吃掉
  [[ "${1:-}" == "--" ]] && shift

  if [[ "$#" -eq 0 ]]; then
    echo "[WARN] --run 沒有附命令，退出 0"; exit 0
  fi
  "$@"
  echo "[OK] command finished without error"
fi
