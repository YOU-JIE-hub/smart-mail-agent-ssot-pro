#!/usr/bin/env bash
set -Eeuo pipefail
export LC_ALL=C
trap 'rc=$?; echo "[EXIT] rc=$rc"; exit $rc' EXIT
trap 'rc=$?; echo "[ERR] line=$LINENO rc=$rc cmd=${BASH_COMMAND}"; exit $rc' ERR

echo "SMA PRINT OK"

# 0) 進專案根 + 環境
SET_ROOT="/home/youjie/projects/smart-mail-agent"
GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "${GIT_ROOT:-}" ] && [ -d "$GIT_ROOT/src" ]; then ROOT="$GIT_ROOT"; else ROOT="$SET_ROOT"; fi
cd "$ROOT" || { echo "[FATAL] cd $ROOT 失敗"; exit 96; }
[ -f ".sma_tools/env_guard.sh" ] && source .sma_tools/env_guard.sh || true
[ -x ".venv/bin/activate" ] && source .venv/bin/activate || true
export PYTHONNOUSERSITE=1
export PYTHONPATH=".:scripts:.sma_tools:${PYTHONPATH:-}"

# 1) 參數（可用環境變數覆寫）
LIMIT="${SMA_DUMP_LIMIT:-300}"      # 預設先處理 300 個文字檔；0=全量
OFFSET="${SMA_DUMP_OFFSET:-0}"      # 從第幾個開始（0-based）
CHUNK_BYTES="${SMA_CHUNK_BYTES:-20480}" # 每分片 20KB
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/code_dump/${TS}"
mkdir -p "$OUT/CONTENTS" "$OUT/logs"

TREE_TXT="$OUT/TREE.txt"
MANIFEST_TSV="$OUT/MANIFEST.tsv"
GIT_TSV="$OUT/GIT_MANIFEST.tsv"
CLASSIFY_TSV="$OUT/CLASSIFY.tsv"
DUPES_TSV="$OUT/DUPLICATES.tsv"
NAME_CONFLICTS_TSV="$OUT/BASENAME_CONFLICTS.tsv"
SUMMARY_MD="$OUT/SUMMARY.md"

# 2) 判斷是否文字/程式碼檔
shopt -s extglob
is_text_like() {
  local f="$1"
  case "$f" in
    *.@(py|sh|bash|zsh|ps1|bat|cmd|yml|yaml|toml|ini|cfg|conf|json|ndjson|csv|tsv|txt|md|rst|html|htm|css|js|ts|sql|jinja|j2|env|service|unit)) return 0 ;;
  esac
  if command -v file >/dev/null 2>&1; then
    file --mime-type -b -- "$f" | grep -qiE 'text|json|xml|yaml|csv|javascript|shellscript' && return 0
  fi
  return 1
}

# 3) 掃描檔案（排除噪音與既有輸出）
echo "[STEP] 掃描檔案樹..."
find . \
  -path './.git' -prune -o \
  -path './.venv' -prune -o \
  -path './__pycache__' -prune -o \
  -path './node_modules' -prune -o \
  -path './reports_auto/code_dump' -prune -o \
  -type f -print | sed 's|^\./||' | sort > "$TREE_TXT"

mapfile -t ALL < "$TREE_TXT"
TOTAL="${#ALL[@]}"
[ "$TOTAL" -gt 0 ] || { echo "[FATAL] 專案內沒有檔案"; exit 97; }
echo "[INFO] TOTAL files = $TOTAL"

# 4) 產出 MANIFEST & GIT（快速顯示進度）
echo -e "path\tsize_bytes\tmtime_iso\tsha256\tis_text" > "$MANIFEST_TSV"
echo -e "path\ttracked\tfirst_commit_iso\tlast_commit_iso\tcommit_count" > "$GIT_TSV"

idx=0
for f in "${ALL[@]}"; do
  ((++idx))
  [ -f "$f" ] || continue
  size="$(stat -c '%s' -- "$f" 2>/dev/null || echo 0)"
  mt_epoch="$(stat -c '%Y' -- "$f" 2>/dev/null || echo 0)"
  mt_iso="$(date -u -d "@$mt_epoch" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "")"
  itext=0; is_text_like "$f" && itext=1
  sha="$(sha256sum -- "$f" | awk '{print $1}')"
  printf "%s\t%s\t%s\t%s\t%s\n" "$f" "$size" "$mt_iso" "$sha" "$itext" >> "$MANIFEST_TSV"

  if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
    tracked=1
    last_commit_iso="$(git log --follow -1 --format=%ad --date=iso-strict -- "$f" || true)"
    first_commit_iso="$(git log --follow --format=%ad --date=iso-strict -- "$f" | tail -n1 || true)"
    commit_count="$(git rev-list --count HEAD -- "$f" 2>/dev/null || echo 0)"
  else
    tracked=0; first_commit_iso=""; last_commit_iso=""; commit_count=0
  fi
  printf "%s\t%s\t%s\t%s\t%s\n" "$f" "$tracked" "$first_commit_iso" "$last_commit_iso" "$commit_count" >> "$GIT_TSV"

  if (( idx % 50 == 0 )); then
    printf "[MANIFEST] %d/%d 完成\r" "$idx" "$TOTAL"
  fi
done
echo; echo "[INFO] MANIFEST 完成：$idx/$TOTAL"

# 5) 新舊分類（以最後 commit 時間；無則用 mtime）
now_epoch="$(date -u +%s)"
echo -e "path\tperiod_tag\tpath_tag" > "$CLASSIFY_TSV"
tail -n +2 "$MANIFEST_TSV" | while IFS=$'\t' read -r path size mtime_iso sha istext; do
  last_commit_iso="$(awk -F'\t' -v p="$path" '$1==p{print $4}' "$GIT_TSV" | head -n1)"
  ref="${last_commit_iso:-$mtime_iso}"
  re=0; [ -n "$ref" ] && re="$(date -u -d "$ref" +%s 2>/dev/null || echo 0)"
  age=99999; [ "$re" -gt 0 ] && age=$(( (now_epoch - re)/86400 ))
  if   [ "$age" -le 30 ]; then per="CURRENT_30D"
  elif [ "$age" -le 90 ]; then per="RECENT_90D"
  else per="LEGACY_OLD"; fi
  case "$path" in
    *legacy*|*Legacy*|*LEGACY*|*archive*|*Archive*|*ARCHIVE*|*.bak*|*_bak*|*bak/*|*.sma_tools.bak*|*_old*|*old/*) ptag="PATH_LEGACY" ;;
    *) ptag="PATH_NORMAL" ;;
  esac
  printf "%s\t%s\t%s\n" "$path" "$per" "$ptag" >> "$CLASSIFY_TSV"
done

# 6) 重複內容 / 同名衝突
echo -e "sha256\tcount\tpaths" > "$DUPES_TSV"
awk -F'\t' 'NR>1{a[$4]=a[$4]?a[$4]"|" $1:$1} END{for(k in a){n=split(a[k],x,"|"); if(n>1)print k"\t"n"\t"a[k]}}' "$MANIFEST_TSV" \
  | sort -t$'\t' -k2,2nr -k1,1 >> "$DUPES_TSV"

echo -e "basename\tcount\tpaths" > "$NAME_CONFLICTS_TSV"
awk -F'\t' 'NR>1{p=$1; n=split(p,seg,"/"); b=seg[n]; h[b]=h[b]?h[b]"|"p:p} END{for(k in h){n=split(h[k],x,"|"); if(n>1)print k"\t"n"\t"h[k]}}' "$MANIFEST_TSV" \
  | sort -t$'\t' -k2,2nr -k1,1 >> "$NAME_CONFLICTS_TSV"

# 7) 只對「文字檔」做內容切片（可見進度；預設先處理 LIMIT 個）
mapfile -t TEXTS < <(awk -F'\t' 'NR>1 && $5=="1"{print $1}' "$MANIFEST_TSV")
TOTAL_TEXT="${#TEXTS[@]}"
echo "[INFO] TEXT files = $TOTAL_TEXT"
start="$OFFSET"
end=$(( LIMIT==0 ? TOTAL_TEXT-1 : OFFSET+LIMIT-1 ))
[ "$end" -ge $((TOTAL_TEXT-1)) ] && end=$((TOTAL_TEXT-1))
[ "$start" -le "$end" ] || { echo "[WARN] 無需處理：OFFSET/LIMIT 超出範圍"; exit 0; }

i="$start"; processed=0
while [ "$i" -le "$end" ]; do
  f="${TEXTS[$i]}"
  dest_dir="$OUT/CONTENTS/$(dirname "$f")"
  mkdir -p "$dest_dir"
  prefix="$OUT/CONTENTS/${f}.p"
  # 清掉舊分片，避免殘留
  rm -f "${prefix}"*.txt 2>/dev/null || true
  # 切片輸出（≤20KB）
  split -b "$CHUNK_BYTES" -d -a 3 --additional-suffix=".txt" -- "$f" "$prefix"
  processed=$((processed+1))
  printf "[DUMP] %d/%d  %s  ->  %s.pXXX.txt\r" "$((processed))" "$((end-start+1))" "$f" "$prefix"
  i=$((i+1))
done
echo; echo "[INFO] 內容切片完成：$processed 個檔案（區間：$start..$end）"

# 8) 總結
{
  echo "# Code Dump Summary"
  echo "root: $ROOT"
  echo "timestamp: $TS"
  echo "total_files: $TOTAL"
  echo "text_files: $TOTAL_TEXT"
  echo "range_dumped: $start..$end  (limit=$LIMIT, offset=$OFFSET)"
  echo
  echo "outputs:"
  echo "- $TREE_TXT"
  echo "- $MANIFEST_TSV"
  echo "- $GIT_TSV"
  echo "- $CLASSIFY_TSV"
  echo "- $DUPES_TSV"
  echo "- $NAME_CONFLICTS_TSV"
  echo "- $OUT/CONTENTS/  (*.p001.txt 起，每片 ≤ ${CHUNK_BYTES}B)"
} | tee "$SUMMARY_MD"

echo "[DONE] 輸出完成：$OUT"
