#!/usr/bin/env bash
set -Eeuo pipefail
set -o errtrace
export LC_ALL=C LANG=C PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
ROOT="${SMA_ROOT:-$PWD}"
OUT="reports_auto/export/code_shards_${TS}"
LOGS=".sma_tools/logs"
mkdir -p "$OUT" "$LOGS"
LOG="$LOGS/sma_dump_shards_${TS}.log"
CRASH="$OUT/CRASH_REPORT_${TS}.md"
BUDGET=${BUDGET:-20000}   # 每個分片最大 20KB
LIST="$OUT/ALL_PATHS_${TS}.txt"
COHORT="$OUT/COHORT_${TS}.tsv"
MANIFEST="$OUT/SHARD_MANIFEST_${TS}.tsv"

on_err(){
  rc=$?
  {
    echo "# CRASH REPORT"
    echo "- rc: $rc"
    echo "- cmd: ${BASH_COMMAND}"
    echo "- log: $LOG"
    echo "## tail(log)"; echo '```'; tail -n 120 "$LOG" 2>/dev/null || true; echo '```'
  } > "$CRASH"
  exit $rc
}
trap on_err ERR
exec > >(tee -a "$LOG") 2>&1

echo "SMA PRINT OK (sharded dump start)"
[ -f .sma_tools/env_guard.sh ] && . .sma_tools/env_guard.sh || true
export PYTHONPATH=".:scripts:.sma_tools:${PYTHONPATH:-}"

# 産生完整檔案清單（排除快取/產物與我們自己的輸出）
find . \
  -path './.git' -prune -o \
  -path './.venv' -prune -o \
  -path './node_modules' -prune -o \
  -path './.hf_cache' -prune -o \
  -path './artifacts' -prune -o \
  -path './artifacts_prod' -prune -o \
  -path './reports_auto' -prune -o \
  -type f \( -iname '*.py' -o -iname '*.sh' -o -iname '*.bash' -o \
             -iname '*.yml' -o -iname '*.yaml' -o -iname '*.json' -o \
             -iname '*.toml' -o -iname '*.ini'  -o -iname '*.cfg'  -o -iname '*.conf' -o \
             -iname '*.md'  -o -iname '*.txt'  -o -iname '*.csv'  -o -iname '*.sql'  -o \
             -iname '*.js'  -o -iname '*.ts' \) \
  -print | sed 's|^\./||' | LC_ALL=C sort > "$LIST"

N=$(wc -l < "$LIST" | tr -d ' ')
if [ "${N:-0}" -eq 0 ]; then
  echo "ROOT=$ROOT" > "$OUT/SHARD_0001.txt"
  echo "[OK] 空專案"
  exit 0
fi

# 初始化第一個分片
shard=1; shard_path=$(printf "%s/SHARD_%04d.txt" "$OUT" "$shard")
bytes_left=$BUDGET
{
  echo "ROOT=$ROOT"
  echo "TS=$TS"
  echo "FILES=$N"
} > "$shard_path"
bytes_left=$(( bytes_left - $(wc -c < "$shard_path") ))

# manifest 表頭
echo -e "shard\tseq\tpath\tpart\tbytes_written" > "$MANIFEST"

seq=0
while IFS= read -r p; do
  seq=$((seq+1))
  header=$(printf "§%d %s\n" "$seq" "$p")
  header_len=${#header}

  # header 塞不下就開新分片
  if [ $header_len -gt $bytes_left ]; then
    shard=$((shard+1)); shard_path=$(printf "%s/SHARD_%04d.txt" "$OUT" "$shard"); : > "$shard_path"
    bytes_left=$BUDGET
  fi
  printf "%s" "$header" >> "$shard_path"
  bytes_left=$((bytes_left - header_len))

  # 寫入完整內容（必要時跨分片續寫）
  total=$(wc -c < "$p" 2>/dev/null | tr -d ' ' || echo 0)
  pos=0; part=1
  while [ "$pos" -lt "$total" ]; do
    if [ $bytes_left -le 0 ]; then
      shard=$((shard+1)); shard_path=$(printf "%s/SHARD_%04d.txt" "$OUT" "$shard"); : > "$shard_path"
      bytes_left=$BUDGET
      cont=$(printf "§%d %s (cont +%d)\n" "$seq" "$p" "$pos")
      cont_len=${#cont}
      if [ $cont_len -gt $bytes_left ]; then
        continue
      fi
      printf "%s" "$cont" >> "$shard_path"
      bytes_left=$((bytes_left - cont_len))
    fi
    can_write=$bytes_left
    remain=$(( total - pos ))
    count=$(( remain<can_write ? remain : can_write ))
    dd if="$p" bs=1 skip="$pos" count="$count" status=none >> "$shard_path" || true
    echo -e "${shard}\t${seq}\t${p}\t${part}\t${count}" >> "$MANIFEST"
    pos=$(( pos + count ))
    bytes_left=$(( bytes_left - count ))
    part=$((part+1))
  done

  # 每個檔案後補換行，塞不下就換下一片
  if [ $bytes_left -le 0 ]; then
    shard=$((shard+1)); shard_path=$(printf "%s/SHARD_%04d.txt" "$OUT" "$shard"); : > "$shard_path"; bytes_left=$BUDGET
  fi
  printf "\n" >> "$shard_path"; bytes_left=$((bytes_left - 1))

  # 進度提示：每處理 200 個檔案印一次
  if (( seq % 200 == 0 )); then
    echo "[PROGRESS] files=${seq} shards=${shard}"
  fi
done < "$LIST"

# 產出新舊分群（mtime）
echo -e "path\tmtime\tcohort" > "$COHORT"
now=$(date +%s)
while IFS= read -r p; do
  mt_epoch=$(stat -c %Y -- "$p" 2>/dev/null || stat -f %m -- "$p" 2>/dev/null || date +%s)
  mt="$(date -u -r "$mt_epoch" +%F 2>/dev/null || date -u +%F)"
  age=$(( (now - mt_epoch)/86400 ))
  cohort="old"; [ $age -le 14 ] && cohort="now"; [ $age -ge 15 ] && [ $age -le 60 ] && cohort="recent"; [ $age -ge 61 ] && [ $age -le 180 ] && cohort="mid"
  printf "%s\t%s\t%s\n" "$p" "$mt" "$cohort" >> "$COHORT"
done < "$LIST"

echo "[OK] 分片輸出完成：$OUT"
ls -1 "$OUT" | sed -n '1,50p'
