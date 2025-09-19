#!/usr/bin/env bash
# 目的：找到最近一次的一鍵錯誤，彙整 run_log / err_log / python stderr / pipeline 片段與 run_dir
set -Eeuo pipefail
ROOT="${SMA_ROOT:-/home/youjie/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo "[FATAL] not found: $ROOT"; exit 2; }

TS="$(date +%Y%m%dT%H%M%S)"
LOGDIR="reports_auto/logs"
STATUSDIR="reports_auto/status"
OUTBASE="reports_auto/errors/CRASH_${TS}"
mkdir -p "$LOGDIR" "$STATUSDIR" "$OUTBASE"

latest_err="$(ls -1t ${LOGDIR}/ONECLICK_ERROR_*.log 2>/dev/null | head -n1 || true)"
if [[ -z "$latest_err" ]]; then
  echo "[WARN] 找不到 ONECLICK_ERROR_*，改用 pipeline.ndjson 末端片段" | tee "${OUTBASE}/COLLECT.log"
  if [[ -f "${LOGDIR}/pipeline.ndjson" ]]; then
    tail -n 200 "${LOGDIR}/pipeline.ndjson" > "${OUTBASE}/pipeline_tail.last200.ndjson"
  else
    echo "[FATAL] 也找不到 pipeline.ndjson，沒有可收集的錯誤來源" | tee -a "${OUTBASE}/COLLECT.log"
  fi
else
  echo "[INFO] latest error = ${latest_err}" | tee "${OUTBASE}/COLLECT.log"
  base_ts="$(basename "$latest_err" | sed -E 's/^ONECLICK_ERROR_([0-9T]+)\.log$/\1/')"
  run_log="${LOGDIR}/ONECLICK_${base_ts}.log"
  status_md="${STATUSDIR}/ONECLICK_${base_ts}.md"
  py_err="${LOGDIR}/E2E_${base_ts}.stderr.log"
  run_dir_guess="$(ls -1d reports_auto/e2e_mail/${base_ts}* 2>/dev/null | head -n1 || true)"

  cp -f "$latest_err" "${OUTBASE}/" 2>/dev/null || true
  [[ -f "$run_log"  ]] && cp -f "$run_log"  "${OUTBASE}/" || echo "[WARN] 缺 ${run_log}"  | tee -a "${OUTBASE}/COLLECT.log"
  [[ -f "$status_md" ]] && cp -f "$status_md" "${OUTBASE}/" || echo "[WARN] 缺 ${status_md}" | tee -a "${OUTBASE}/COLLECT.log"
  [[ -f "$py_err"   ]] && cp -f "$py_err"   "${OUTBASE}/" || echo "[WARN] 缺 ${py_err}"   | tee -a "${OUTBASE}/COLLECT.log"
  [[ -n "$run_dir_guess" ]] && { mkdir -p "${OUTBASE}/run_dir"; cp -rf "$run_dir_guess" "${OUTBASE}/run_dir/" 2>/dev/null || true; }

  {
    echo "# Crash Bundle"
    echo "ROOT: ${ROOT}"
    echo "latest_err: ${latest_err}"
    echo "run_log: ${run_log}"
    echo "status_md: ${status_md}"
    echo "py_err: ${py_err}"
    echo "run_dir: ${run_dir_guess:-<none>}"
    echo
    echo "## System"
    echo "python: $(python -V 2>&1 || true)"
    echo "pip freeze (top 50):"
    pip freeze 2>/dev/null | head -n 50 || true
    echo
    echo "## Disk usage"
    df -h || true
  } > "${OUTBASE}/README.txt"
fi

[[ -f "${LOGDIR}/pipeline.ndjson" ]] && tail -n 200 "${LOGDIR}/pipeline.ndjson" > "${OUTBASE}/pipeline_tail.last200.ndjson" || true

if command -v wslpath >/dev/null 2>&1; then
  WIN_PATH="$(wslpath -w "${OUTBASE}")"
  explorer.exe "${WIN_PATH}" >/dev/null 2>&1 || true
fi

echo "[OK] 錯誤資料已彙整到：${OUTBASE}"
