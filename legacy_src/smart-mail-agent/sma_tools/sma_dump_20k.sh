#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace
export LC_ALL=C LANG=C PYTHONNOUSERSITE=1
TS="$(date +%Y%m%dT%H%M%S)"; ROOT="${SMA_ROOT:-$PWD}"
OUT="reports_auto/export"; LOGS=".sma_tools/logs"
mkdir -p "$OUT" "$LOGS"
LOG="$LOGS/sma_dump_${TS}.log"
CRASH="$OUT/CRASH_REPORT_${TS}.md"
DUMP="$OUT/CODE_DUMP_${TS}.md"
INDEX="$OUT/CODE_INDEX_${TS}.tsv"
COHORT="$OUT/CODE_COHORT_${TS}.tsv"
DUPES="$OUT/CODE_DUPES_${TS}.tsv"
SUMMARY="$OUT/CODE_SUMMARY_${TS}.txt"
MAX_BYTES=${MAX_BYTES:-20000}; MAX_FILES=${MAX_FILES:-30}
on_err(){ rc=$?; { echo "# CRASH REPORT"; echo "- rc: $rc"; echo "- cmd: ${BASH_COMMAND}";
  echo "- root: $ROOT"; echo "- log: $LOG"; echo "## tail(log)"; echo '```'; tail -n 120 "$LOG" 2>/dev/null || true; echo '```'; } >"$CRASH"; exit "$rc"; }
trap on_err ERR
exec > >(tee -a "$LOG") 2>&1
echo "SMA PRINT OK (dump start)"

# 進環境（若有）
[ -f .sma_tools/env_guard.sh ] && . .sma_tools/env_guard.sh || true
export PYTHONPATH=".:scripts:.sma_tools:${PYTHONPATH:-}"

_has(){ command -v "$1" >/dev/null 2>&1; }
HAS_GIT=$(_has git && echo yes || echo no)
STAT_BYTES(){ stat -c %s -- "$1" 2>/dev/null || stat -f %z -- "$1" 2>/dev/null || wc -c <"$1"; }
SHA256(){ p="$1"; if command -v sha256sum >/dev/null 2>&1; then sha256sum -- "$p" | awk '{print $1}';
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 -- "$p" | awk '{print $1}';
  else python3 - "$p" <<PY 2>/dev/null || echo NA
import sys,hashlib
h=hashlib.sha256()
with open(sys.argv[1],'rb') as f:
  for ch in iter(lambda:f.read(1<<20), b''): h.update(ch)
print(h.hexdigest())
PY
  fi; }
IS_TEXT(){ case "$1" in *.py|*.sh|*.bash|*.yml|*.yaml|*.json|*.toml|*.ini|*.cfg|*.conf|*.md|*.txt|*.csv|*.sql|*.js|*.ts) return 0;; esac; return 1; }

# 收集候選（排除重量目錄）
CAND="$(mktemp)"; SEL="$(mktemp)"
find . \
  -path './.git' -prune -o -path './.venv' -prune -o -path './node_modules' -prune -o \
  -path './artifacts' -prune -o -path './artifacts_prod' -prune -o -path './data' -prune -o \
  -path './downloads' -prune -o -path './dist' -prune -o -path './out' -prune -o -path './build' -prune -o \
  -path './reports_auto' -prune -o -path '*/__pycache__' -prune -o \
  -type f \( -iname '*.py' -o -iname '*.sh' -o -iname '*.bash' -o -iname '*.yml' -o -iname '*.yaml' -o -iname '*.json' -o -iname '*.toml' -o -iname '*.ini' -o -iname '*.cfg' -o -iname '*.conf' -o -iname '*.md' -o -iname '*.txt' -o -iname '*.csv' -o -iname '*.sql' -o -iname '*.js' -o -iname '*.ts' \) \
  -print | sed 's|^\./||' | LC_ALL=C sort > "$CAND"

# 以「檔案大小由小到大」→ 再以「重要度」次序（確保一定挑得到）：
score(){ p="$1"; w=10; case "$p" in src/*.py|src/*/*.py|src/*/*/*.py) w=100;; smart_mail_agent/*|src/smart_mail_agent/*) w=98;;
  ai_rpa/*|src/ai_rpa/*) w=96;; scripts/*) w=92;; tests/*) w=88;; .sma_tools/*) w=80;; docs/*|README.*|*/README.*) w=50;; esac; echo "$w"; }
echo -e "bytes\tscore\tpath" > "$SEL"
while IFS= read -r f; do
  IS_TEXT "$f" || continue
  b=$(STAT_BYTES "$f"); s=$(score "$f")
  printf "%08d\t%03d\t%s\n" "$b" "$s" "$f" >> "$SEL"
done < "$CAND"
# 先按 bytes 升冪，再按 score 降冪，再按 path
SEL_SORTED="$(mktemp)"
LC_ALL=C sort -k1,1n -k2,2r -k3,3 "$SEL" > "$SEL_SORTED"

# 產出：≤30 檔、合計 ≤20KB（完整內容）
TOTAL=0; COUNT=0
echo -e "score\tbytes\tpath" > "$INDEX"
{ echo "# CODE DUMP (≤${MAX_FILES} files, ≤${MAX_BYTES} bytes) @ ${TS}"; echo; } > "$DUMP"
while IFS=$'\t' read -r b s f; do
  [ "$b" = "bytes" ] && continue
  [ $COUNT -ge $MAX_FILES ] && break
  nb=$((TOTAL + b)); [ $nb -gt $MAX_BYTES ] && continue
  echo "-----8<----- FILE: $f (${b} bytes)" >> "$DUMP"; cat -- "$f" >> "$DUMP"; echo "-----8<----- END $f" >> "$DUMP"
  printf "%s\t%s\t%s\n" "$s" "$b" "$f" >> "$INDEX"
  TOTAL=$nb; COUNT=$((COUNT+1))
done < "$SEL_SORTED"

# 若仍選不到，直接回報最小的 1 檔尺寸超過 20KB 的事實
if [ $COUNT -eq 0 ]; then
  smallest="$(awk -F'\t' 'NR==2{print $3" ("$1" bytes)"}' "$SEL_SORTED" 2>/dev/null || true)"
  { echo "No file fits into 20KB total budget."; echo "Smallest candidate: ${smallest:-NA}"; } >> "$DUMP"
fi
echo "[INFO] Selected files: $COUNT | Total bytes: $TOTAL"

# 同期分群（mtime；無 git 也可）：now<=14d, recent 15-60d, mid 61-180d, old>180d
echo -e "path\tmtime\tcohort" > "$COHORT"
now=$(date +%s)
awk -F'\t' 'NR>1{print $3"\t"$2}' "$INDEX" | while IFS=$'\t' read -r f b; do
  mt_epoch=$(stat -c %Y -- "$f" 2>/dev/null || stat -f %m -- "$f" 2>/dev/null || date +%s)
  mt="$(date -u -r "$mt_epoch" +%F 2>/dev/null || date -u +%F)"
  age=$(( (now - mt_epoch)/86400 ))
  cohort="old"; [ $age -le 14 ] && cohort="now"; [ $age -ge 15 ] && [ $age -le 60 ] && cohort="recent"; [ $age -ge 61 ] && [ $age -le 180 ] && cohort="mid"
  echo -e "${f}\t${mt}\t${cohort}" >> "$COHORT"
done

# 重複群組（sha256）
echo -e "sha256\tbytes\tpath" > "$DUPES"
awk -F'\t' 'NR>1{print $3"\t"$2}' "$INDEX" | while IFS=$'\t' read -r f b; do
  echo -e "$(SHA256 "$f")\t$b\t$f" >> "$DUPES"
done

# 摘要
{
  echo "Snapshot@${TS}"; echo "ROOT=$ROOT"
  echo "Selected files: $COUNT"; echo "Total bytes: $TOTAL (limit=${MAX_BYTES})"
  echo; echo "[Cohort breakdown]"; cut -f3 "$COHORT" | tail -n +2 | sort | uniq -c | awk '{printf "%s\t%s\n",$2,$1}'
} > "$SUMMARY"

# 終端顯示
echo; echo "================== CODE INDEX ==================";  sed -n "1,200p" "$INDEX"
echo; echo "================== COHORT (新舊分群) ==========";  sed -n "1,200p" "$COHORT"
echo; echo "================== CODE DUMP (全文≤20KB) =====";  sed -n "1,200000p" "$DUMP"
echo; echo "[OK] 輸出：" "$DUMP" "$INDEX" "$COHORT" "$DUPES" "$SUMMARY"
