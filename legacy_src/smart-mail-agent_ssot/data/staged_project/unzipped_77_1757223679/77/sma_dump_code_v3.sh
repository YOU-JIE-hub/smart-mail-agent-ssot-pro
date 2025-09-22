#!/usr/bin/env bash
set -Eeuo pipefail
set -o pipefail
export LC_ALL=C

trap 'rc=$?; echo "[EXIT] rc=$rc"; exit $rc' EXIT
trap 'rc=$?; echo "[ERR] line=$LINENO rc=$rc cmd=${BASH_COMMAND}"; exit $rc' ERR

echo "SMA PRINT OK"

# --- 0) 專案根定位（先用 git，再用固定路徑） ---
SET_ROOT="/home/youjie/projects/smart-mail-agent"
GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "${GIT_ROOT:-}" ] && [ -d "$GIT_ROOT" ]; then
  ROOT="$GIT_ROOT"
else
  ROOT="$SET_ROOT"
fi
cd "$ROOT"
echo "[INFO] repo root = $ROOT"

# --- 1) 啟環境與固定變數（僅若存在） ---
[ -f ".sma_tools/env_guard.sh" ] && source .sma_tools/env_guard.sh || true
[ -x ".venv/bin/activate" ] && source .venv/bin/activate || true
export PYTHONNOUSERSITE=1
export PYTHONPATH=".:scripts:.sma_tools:${PYTHONPATH:-}"

# --- 2) 準備輸出目錄 ---
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/code_dump/${TS}"
mkdir -p "$OUT"/{CONTENTS,logs}
TREE_TXT="$OUT/TREE.txt"
MANIFEST_TSV="$OUT/MANIFEST.tsv"
GIT_TSV="$OUT/GIT_MANIFEST.tsv"
CLASSIFY_TSV="$OUT/CLASSIFY.tsv"
DUPES_TSV="$OUT/DUPLICATES.tsv"
NAME_CONFLICTS_TSV="$OUT/BASENAME_CONFLICTS.tsv"
SUMMARY_MD="$OUT/SUMMARY.md"

# --- 3) 判斷是否「程式碼/文字」檔（副檔名 + MIME） ---
shopt -s extglob
is_text_like() {
  local f="$1"
  case "$f" in
    *.@(py|sh|bash|zsh|ps1|bat|cmd|yml|yaml|toml|ini|cfg|conf|json|ndjson|csv|tsv|txt|md|rst|html|htm|css|js|ts|sql|jinja|j2|env|service|unit)) return 0 ;;
  esac
  if command -v file >/dev/null 2>&1; then
    file --mime-type -b -- "$f" | grep -qiE 'text|json|xml|yaml|csv|javascript|shellscript' && return 0 || return 1
  fi
  return 1
}

# --- 4) 掃描檔案樹（排除雜訊與本工具輸出） ---
echo "[STEP] 掃描檔案樹..."
find . \
  -path './.git' -prune -o \
  -path './.venv' -prune -o \
  -path './__pycache__' -prune -o \
  -path './node_modules' -prune -o \
  -path './reports_auto/code_dump' -prune -o \
  -type f -print | sed 's|^\./||' | sort > "$TREE_TXT"

mapfile -t FILES < "$TREE_TXT"
[ "${#FILES[@]}" -gt 0 ] || { echo "[FATAL] 專案內沒有檔案可掃描"; exit 97; }

# --- 5) 產出 MANIFEST 與 GIT 資訊（大小、時間、雜湊、是否文字） ---
echo -e "path\tsize_bytes\tmtime_iso\tsha256\tis_text" > "$MANIFEST_TSV"
echo -e "path\ttracked\tfirst_commit_iso\tlast_commit_iso\tcommit_count" > "$GIT_TSV"

for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  size="$(stat -c '%s' -- "$f" 2>/dev/null || echo 0)"
  mtime_epoch="$(stat -c '%Y' -- "$f" 2>/dev/null || echo 0)"
  mtime_iso="$(date -u -d "@$mtime_epoch" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "")"
  sha="$(sha256sum -- "$f" | awk '{print $1}')"
  itext=0; is_text_like "$f" && itext=1
  printf "%s\t%s\t%s\t%s\t%s\n" "$f" "$size" "$mtime_iso" "$sha" "$itext" >> "$MANIFEST_TSV"

  if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
    tracked=1
    last_commit_iso="$(git log --follow -1 --format=%ad --date=iso-strict -- "$f" || true)"
    first_commit_iso="$(git log --follow --format=%ad --date=iso-strict -- "$f" | tail -n1 || true)"
    commit_count="$(git rev-list --count HEAD -- "$f" 2>/dev/null || echo 0)"
  else
    tracked=0
    first_commit_iso=""
    last_commit_iso=""
    commit_count=0
  fi
  printf "%s\t%s\t%s\t%s\t%s\n" "$f" "$tracked" "$first_commit_iso" "$last_commit_iso" "$commit_count" >> "$GIT_TSV"
done

# --- 6) 初步新舊分類（CURRENT_30D / RECENT_90D / LEGACY_OLD；PATH_LEGACY） ---
now_epoch="$(date -u +%s)"
echo -e "path\tperiod_tag\tpath_tag" > "$CLASSIFY_TSV"
tail -n +2 "$MANIFEST_TSV" | while IFS=$'\t' read -r path size mtime_iso sha istext; do
  last_commit_iso="$(awk -F'\t' -v p="$path" '$1==p{print $4}' "$GIT_TSV" | head -n1)"
  ref_time="${last_commit_iso:-$mtime_iso}"
  ref_epoch=0
  [ -n "$ref_time" ] && ref_epoch="$(date -u -d "$ref_time" +%s 2>/dev/null || echo 0)"
  age_days=99999
  [ "$ref_epoch" -gt 0 ] && age_days=$(( (now_epoch - ref_epoch)/86400 ))
  if   [ "$age_days" -le 30 ]; then period="CURRENT_30D"
  elif [ "$age_days" -le 90 ]; then period="RECENT_90D"
  else period="LEGACY_OLD"; fi
  case "$path" in
    *legacy*|*Legacy*|*LEGACY*|*archive*|*Archive*|*ARCHIVE*|*.bak*|*_bak*|*bak/*|*.sma_tools.bak*|*_old*|*old/*) ptag="PATH_LEGACY" ;;
    *) ptag="PATH_NORMAL" ;;
  esac
  printf "%s\t%s\t%s\n" "$path" "$period" "$ptag" >> "$CLASSIFY_TSV"
done

# --- 7) 重複內容與同名衝突 ---
echo -e "sha256\tcount\tpaths" > "$DUPES_TSV"
awk -F'\t' 'NR>1{a[$4]=a[$4]?a[$4]"|" $1:$1} END{for(k in a){n=split(a[k],x,"|"); if(n>1)print k"\t"n"\t"a[k]}}' "$MANIFEST_TSV" \
  | sort -t$'\t' -k2,2nr -k1,1 >> "$DUPES_TSV"

echo -e "basename\tcount\tpaths" > "$NAME_CONFLICTS_TSV"
awk -F'\t' 'NR>1{p=$1; n=split(p,seg,"/"); b=seg[n]; h[b]=h[b]?h[b]"|"p:p} END{for(k in h){n=split(h[k],x,"|"); if(n>1)print k"\t"n"\t"h[k]}}' "$MANIFEST_TSV" \
  | sort -t$'\t' -k2,2nr -k1,1 >> "$NAME_CONFLICTS_TSV"

# --- 8) 內容輸出：每個「文字檔」切片 <= 20KB，多片輸出至 OUT/CONTENTS/<原路徑>.pNNN.txt ---
#     二進位或非文字檔不輸出內容，只在 MANIFEST 列出
while IFS=$'\t' read -r path size mtime_iso sha istext; do
  [ "$path" = "path" ] && continue
  [ -f "$path" ] || continue
  [ "$istext" -eq 1 ] || continue
  dest_dir="$OUT/CONTENTS/$(dirname "$path")"
  mkdir -p "$dest_dir"
  prefix="$OUT/CONTENTS/${path}.p"
  # split 以 20*1024 bytes 切割；數字後綴長度 3，從 001 起
  split -b 20480 -d -a 3 --additional-suffix=".txt" -- "$path" "$prefix"
done < "$MANIFEST_TSV"

# --- 9) 總結輸出 ---
{
  echo "# Code Dump Summary"
  echo
  echo "根目錄：$ROOT"
  echo "時間戳：$TS"
  echo
  echo "主要輸出："
  echo "- $TREE_TXT"
  echo "- $MANIFEST_TSV"
  echo "- $GIT_TSV"
  echo "- $CLASSIFY_TSV"
  echo "- $DUPES_TSV"
  echo "- $NAME_CONFLICTS_TSV"
  echo "- $OUT/CONTENTS/  （所有文字檔已切片輸出，*.p001.txt 起）"
  echo
  echo "規則："
  echo "- 只輸出「文字/程式碼檔」的內容；二進位/大型模型只列在 MANIFEST。"
  echo "- 新舊分群：CURRENT_30D / RECENT_90D / LEGACY_OLD；以及 PATH_LEGACY 標記。"
} | tee "$SUMMARY_MD"

echo "[DONE] 輸出完成：$OUT"
