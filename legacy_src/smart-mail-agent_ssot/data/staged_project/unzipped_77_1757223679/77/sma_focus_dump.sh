#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C
trap 'rc=$?; echo "[EXIT] rc=$rc"; exit $rc' EXIT
trap 'rc=$?; echo "[ERR] line=$LINENO rc=$rc cmd=${BASH_COMMAND}"; exit $rc' ERR

echo "SMA PRINT OK"

# 0) 進專案 + 環境
SET_ROOT="/home/youjie/projects/smart-mail-agent"
GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "${GIT_ROOT:-}" ] && [ -d "$GIT_ROOT/src" ]; then ROOT="$GIT_ROOT"; else ROOT="$SET_ROOT"; fi
cd "$ROOT" || { echo "[FATAL] cd $ROOT 失敗"; exit 96; }
[ -f ".sma_tools/env_guard.sh" ] && source .sma_tools/env_guard.sh || true
[ -x ".venv/bin/activate" ] && source .venv/bin/activate || true
export PYTHONNOUSERSITE=1
export PYTHONPATH=".:scripts:.sma_tools:${PYTHONPATH:-}"

# 1) 自動抓「最新一次」focus 清單
BASE="reports_auto/code_focus"
LATEST="$(ls -1dt ${BASE}/* 2>/dev/null | head -n1 || true)"
[ -n "$LATEST" ] || { echo "[FATAL] 找不到 $BASE 的輸出"; exit 97; }

FOCUS_TXT="$LATEST/FOCUS_FILES.txt"
OUT_DIR="$LATEST/CONTENTS"
mkdir -p "$OUT_DIR"

# 2) 參數
CHUNK_BYTES="${SMA_CHUNK_BYTES:-20480}"   # 每片 20KB
LIMIT="${SMA_DUMP_LIMIT:-0}"              # 0=全量；>0：只前 N 個
OFFSET="${SMA_DUMP_OFFSET:-0}"

mapfile -t FILES < "$FOCUS_TXT"
TOTAL="${#FILES[@]}"
[ "$TOTAL" -gt 0 ] || { echo "[FATAL] 清單為空：$FOCUS_TXT"; exit 98; }
echo "[INFO] FOCUS files = $TOTAL  (from $FOCUS_TXT)"

start="$OFFSET"
end=$(( LIMIT==0 ? TOTAL-1 : OFFSET+LIMIT-1 ))
[ "$end" -ge $((TOTAL-1)) ] && end=$((TOTAL-1))
[ "$start" -le "$end" ] || { echo "[WARN] 無需處理：OFFSET/LIMIT 超出範圍"; exit 0; }

# 3) 逐檔切片（顯示進度）
i="$start"; processed=0
while [ "$i" -le "$end" ]; do
  f="${FILES[$i]}"
  [ -f "$f" ] || { i=$((i+1)); continue; }
  dest_dir="$OUT_DIR/$(dirname "$f")"
  mkdir -p "$dest_dir"
  prefix="$dest_dir/$(basename "$f").p"
  rm -f "${prefix}"*.txt 2>/dev/null || true
  split -b "$CHUNK_BYTES" -d -a 3 --additional-suffix=".txt" -- "$f" "$prefix"
  processed=$((processed+1))
  printf "[DUMP] %d/%d  %s  ->  %s.pXXX.txt\r" "$processed" "$((end-start+1))" "$f" "$prefix"
  i=$((i+1))
done
echo; echo "[INFO] 內容切片完成：$processed 個檔案（區間：$start..$end）"
echo "[DONE] 輸出完成：$OUT_DIR"
