#!/usr/bin/env bash
set -Eeuo pipefail; set -o errtrace
export LC_ALL=C LANG=C PYTHONNOUSERSITE=1
TS="$(date +%Y%m%dT%H%M%S)"
ROOT="${SMA_ROOT:-$PWD}"
OUTDIR="reports_auto/export"; LOGDIR=".sma_tools/logs"
mkdir -p "$OUTDIR" "$LOGDIR"
LOG="$LOGDIR/sma_dump_${TS}.log"
CRASH="$OUTDIR/CRASH_REPORT_${TS}.md"
DUMP="$OUTDIR/CODE_DUMP_${TS}.md"
INDEX="$OUTDIR/CODE_INDEX_${TS}.tsv"
COHORT="$OUTDIR/CODE_COHORT_${TS}.tsv"
DUPES="$OUTDIR/CODE_DUPES_${TS}.tsv"
SUMMARY="$OUTDIR/CODE_SUMMARY_${TS}.txt"
MAX_BYTES=${MAX_BYTES:-20000}; MAX_FILES=${MAX_FILES:-30}

on_err(){ rc=$?; {
  echo "# CRASH REPORT"
  echo "- when: $TS"
  echo "- rc: $rc"
  echo "- cmd: ${BASH_COMMAND}"
  echo "- root: $ROOT"
  echo "- log: $LOG"
  echo "## tail(log)"; echo '```'; tail -n 120 "$LOG" 2>/dev/null || true; echo '```'
} >"$CRASH"; exit "$rc"; }; trap on_err ERR
exec > >(tee -a "$LOG") 2>&1
echo "SMA PRINT OK (dump start)"

_has(){ command -v "$1" >/dev/null 2>&1; }
HAS_GIT=$(_has git && echo yes || echo no)
HAS_SHA256SUM=$(_has sha256sum && echo yes || echo no)

STAT_BYTES(){ stat -c %s -- "$1" 2>/dev/null || stat -f %z -- "$1" 2>/dev/null || wc -c <"$1"; }
SHA256(){ p="$1"; if [ "$HAS_SHA256SUM" = "yes" ]; then sha256sum -- "$p" | awk '{print $1}'; else python3 - "$p" <<PY 2>/dev/null || echo NA
import sys,hashlib
h=hashlib.sha256()
with open(sys.argv[1],'rb') as f:
  for ch in iter(lambda:f.read(1<<20), b''): h.update(ch)
print(h.hexdigest())
PY
fi; }

IS_TEXT(){ case "$1" in *.py|*.sh|*.bash|*.yml|*.yaml|*.json|*.toml|*.ini|*.cfg|*.conf|*.md|*.txt|*.csv|*.sql|*.js|*.ts) return 0;; esac; return 1; }
score_path(){ p="$1"; w=10
  case "$p" in src/*.py|src/*/*.py|src/*/*/*.py) w=100;;
    smart_mail_agent/*|src/smart_mail_agent/*) w=98;;
    ai_rpa/*|src/ai_rpa/*) w=96;; scripts/*) w=92;;
    tests/*) w=88;; .sma_tools/*) w=80;;
    docs/*|README.*|*/README.*) w=50;; esac; echo "$w"; }

# 收集候選
CAND_TMP="$(mktemp)"; SEL_TMP="$(mktemp)"
find . \
  -path "./.git" -prune -o -path "./.venv" -prune -o -path "./node_modules" -prune -o \
  -path "./artifacts" -prune -o -path "./artifacts_prod" -prune -o -path "./reports_auto" -prune -o \
  -path "./data" -prune -o -path "./downloads" -prune -o -path "./dist" -prune -o -path "./out" -prune -o \
  -path "./build" -prune -o -path "*/__pycache__" -prune -o \
  -type f \( -iname "*.py" -o -iname "*.sh" -o -iname "*.bash" -o -iname "*.yml" -o -iname "*.yaml" -o -iname "*.json" -o -iname "*.toml" -o -iname "*.ini" -o -iname "*.cfg" -o -iname "*.conf" -o -iname "*.md" -o -iname "*.txt" -o -iname "*.csv" -o -iname "*.sql" -o -iname "*.js" -o -iname "*.ts" \) \
  -print | sed "s|^\./||" | LC_ALL=C sort > "$CAND_TMP"

# 打分/排序
echo -e "score\tbytes\tpath" > "$INDEX"
while IFS= read -r f; do IS_TEXT "$f" || continue
  b=$(STAT_BYTES "$f"); s=$(score_path "$f"); printf "%03d\t%08d\t%s\n" "$s" "$b" "$f" >> "$SEL_TMP"
done < "$CAND_TMP"
LC_ALL=C sort -r -k1,1 -k3,3 "$SEL_TMP" -o "$SEL_TMP"

# 生成 DUMP（≤30 檔，≤20KB）
TOTAL=0; COUNT=0
{ echo "# CODE DUMP (≤${MAX_FILES} files, ≤${MAX_BYTES} bytes) @ ${TS}"; echo; } > "$DUMP"
while IFS=$'\t' read -r sc b f; do
  [ "$sc" = "score" ] && continue
  [ $COUNT -ge $MAX_FILES ] && break
  nb=$((TOTAL + b)); [ $nb -gt $MAX_BYTES ] && continue
  echo "-----8<----- FILE: $f (${b} bytes)" >> "$DUMP"; cat -- "$f" >> "$DUMP"; echo "-----8<----- END $f" >> "$DUMP"
  printf "%s\t%s\t%s\n" "$sc" "$b" "$f" >> "$INDEX"
  TOTAL=$nb; COUNT=$((COUNT+1))
done < "$SEL_TMP"
echo "[INFO] Selected files: $COUNT | Total bytes: $TOTAL"

# 同期分群（用 mtime；避免 date -d 相依）
echo -e "path\tmtime\tcohort" > "$COHORT"
now_epoch=$(date +%s)
while IFS=$'\t' read -r sc b f; do
  [ "$sc" = "score" ] && continue
  mt_epoch=$(stat -c %Y -- "$f" 2>/dev/null || stat -f %m -- "$f" 2>/dev/null || date +%s)
  mt="$(date -u -r "$mt_epoch" +%F 2>/dev/null || date -u +%F)"
  age_days=$(( (now_epoch - mt_epoch) / 86400 ))
  cohort="old"; [ $age_days -le 14 ] && cohort="now"
  [ $age_days -ge 15 ] && [ $age_days -le 60 ] && cohort="recent"
  [ $age_days -ge 61 ] && [ $age_days -le 180 ] && cohort="mid"
  echo -e "${f}\t${mt}\t${cohort}" >> "$COHORT"
done < "$INDEX"

# 重複檔
echo -e "sha256\tbytes\tpath" > "$DUPES"
awk -F'\t' 'NR>1{print $3"\t"$2}' "$INDEX" | while IFS=$'\t' read -r f b; do
  sum="$(SHA256 "$f")"; echo -e "${sum}\t${b}\t${f}" >> "$DUPES"
done

# 摘要（避免 awk 內部函式造成括號誤判，用 uniq -c）
{
  echo "Snapshot@${TS}"
  echo "ROOT=$ROOT"
  echo "Selected files: $COUNT"
  echo "Total bytes: $TOTAL (limit=${MAX_BYTES})"
  echo
  echo "[Cohort breakdown]"
  cut -f3 "$COHORT" | tail -n +2 | sort | uniq -c | awk '{printf "%s\t%s\n",$2,$1}'
} > "$SUMMARY"

# 終端輸出
echo; echo "================== CODE INDEX ==================";  sed -n "1,200p" "$INDEX"
echo; echo "================== COHORT (分群) ===============" ; sed -n "1,200p" "$COHORT"
echo; echo "================== CODE DUMP (全文≤20KB) ======="; sed -n "1,200000p" "$DUMP"
echo; echo "[OK] 輸出：" "$DUMP" "$INDEX" "$COHORT" "$DUPES" "$SUMMARY"
