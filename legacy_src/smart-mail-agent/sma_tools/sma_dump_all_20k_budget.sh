#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace
export LC_ALL=C LANG=C PYTHONNOUSERSITE=1
TS="$(date +%Y%m%dT%H%M%S)"; ROOT="${SMA_ROOT:-$PWD}"
OUT="reports_auto/export"; LOGS=".sma_tools/logs"
mkdir -p "$OUT" "$LOGS"
LOG="$LOGS/sma_dump_all_${TS}.log"
CRASH="$OUT/CRASH_REPORT_${TS}.md"
BUDGET=${BUDGET:-20000}   # 總上限（bytes）
DUMP="$OUT/ALL_CODE_BUDGETED_${TS}.txt"   # 你要的最終單一輸出檔（≤BUDGET）
ALL="$OUT/ALL_PATHS_${TS}.txt"            # 全部檔案路徑（無上限）
COHORT="$OUT/ALL_COHORT_${TS}.tsv"        # 新舊分群（mtime）

on_err(){ rc=$?; {
  echo "# CRASH REPORT"; echo "- rc: $rc"; echo "- cmd: ${BASH_COMMAND}"; echo "- log: $LOG";
  echo "## tail(log)"; echo '```'; tail -n 120 "$LOG" 2>/dev/null || true; echo '```';
} >"$CRASH"; exit $rc; }; trap on_err ERR

exec > >(tee -a "$LOG") 2>&1
echo "SMA PRINT OK (budget dump start)"
# 永遠先進環境
[ -f .sma_tools/env_guard.sh ] && . .sma_tools/env_guard.sh || true
export PYTHONPATH=".:scripts:.sma_tools:${PYTHONPATH:-}"

# 收集「所有代碼/文字檔」路徑（排除產物與快取）
find . \
  -path './.git' -prune -o -path './.venv' -prune -o -path './node_modules' -prune -o \
  -path './artifacts' -prune -o -path './artifacts_prod' -prune -o -path './reports_auto' -prune -o \
  -path './data' -prune -o -path './dist' -prune -o -path './out' -prune -o -path './build' -prune -o \
  -path './.hf_cache' -prune -o -path '*/__pycache__' -prune -o \
  -type f \( -iname '*.py' -o -iname '*.sh' -o -iname '*.bash' -o -iname '*.yml' -o -iname '*.yaml' -o \
             -iname '*.json' -o -iname '*.toml' -o -iname '*.ini' -o -iname '*.cfg' -o -iname '*.conf' -o \
             -iname '*.md'  -o -iname '*.txt' -o -iname '*.csv' -o -iname '*.sql' -o -iname '*.js'  -o -iname '*.ts' \) \
  -print | sed 's|^\./||' | LC_ALL=C sort > "$ALL"

N=$(wc -l < "$ALL" | tr -d ' ')
[ "${N:-0}" -eq 0 ] && { printf "ROOT=%s\nTS=%s\nFILES=0\n" "$ROOT" "$TS" > "$DUMP"; echo "[OK] 無檔可輸出 -> $DUMP"; exit 0; }

# 計算每檔的 header 成本：格式「§序號 路徑\n」
HEADER_BYTES=$(awk '{sum+=1 + length(sprintf("%d", NR)) + 1 + length($0) + 1} END{print sum}' "$ALL")
HEADER_STATIC=64  # ROOT/TS/FILES 標頭的保守估計
CONTENT_BUDGET=$(( BUDGET - HEADER_STATIC - HEADER_BYTES ))
[ $CONTENT_BUDGET -lt 0 ] && CONTENT_BUDGET=0
PER=$(( N>0 ? CONTENT_BUDGET / N : 0 ))  # 平均分配的每檔內容額度（bytes，可能為0）

TMP="$(mktemp)"
{
  echo "ROOT=$ROOT"
  echo "TS=$TS"
  echo "FILES=$N"
} > "$TMP"

i=0
while IFS= read -r p; do
  i=$((i+1))
  printf "§%d %s\n" "$i" "$p" >> "$TMP"
  if [ "$PER" -gt 0 ]; then
    { head -c "$PER" -- "$p" 2>/dev/null || head -c "$PER" "$p" 2>/dev/null || true; } >> "$TMP"
    printf "\n" >> "$TMP"
  fi
done < "$ALL"

# 強制總長度 ≤ BUDGET
SIZE=$(wc -c < "$TMP" | tr -d ' ')
if [ "$SIZE" -gt "$BUDGET" ]; then
  head -c "$BUDGET" "$TMP" > "$DUMP"
else
  mv "$TMP" "$DUMP"
fi
rm -f "$TMP"

# 產出新舊分群（mtime）
echo -e "path\tmtime\tcohort" > "$COHORT"
now=$(date +%s)
while IFS= read -r p; do
  mt_epoch=$(stat -c %Y -- "$p" 2>/dev/null || stat -f %m -- "$p" 2>/dev/null || date +%s)
  mt="$(date -u -r "$mt_epoch" +%F 2>/dev/null || date -u +%F)"
  age=$(( (now - mt_epoch)/86400 ))
  cohort="old"; [ $age -le 14 ] && cohort="now"; [ $age -ge 15 ] && [ $age -le 60 ] && cohort="recent"; [ $age -ge 61 ] && [ $age -le 180 ] && cohort="mid"
  printf "%s\t%s\t%s\n" "$p" "$mt" "$cohort" >> "$COHORT"
done < "$ALL"

echo "[OK] 路徑清單 -> $ALL"
echo "[OK] 均分內容輸出 -> $DUMP (總≤${BUDGET}B，N=$N，每檔額度=$PER B)"
echo "[OK] 新舊分群 -> $COHORT"
# 同步在終端顯示前 400 行，方便你立即複製
sed -n '1,400p' "$DUMP"
