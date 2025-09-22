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

# 1) 只鎖定這些「代碼目錄」
INCLUDE_DIRS=(src ai_rpa scripts smart_mail_agent tests tests_smoke .github docs tools examples legacy_tests)

# 2) 準備輸出
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/code_focus/${TS}"
mkdir -p "$OUT"
FOCUS_TXT="$OUT/FOCUS_FILES.txt"
MANIFEST_TSV="$OUT/MANIFEST.tsv"
GIT_TSV="$OUT/GIT_MANIFEST.tsv"
CLASSIFY_TSV="$OUT/CLASSIFY.tsv"
SUMMARY_MD="$OUT/SUMMARY.md"

# 3) 掃描（只在包含目錄內、排除雜訊）
echo "[STEP] 列出代碼清單..."
> "$FOCUS_TXT"
for d in "${INCLUDE_DIRS[@]}"; do
  [ -d "$d" ] || continue
  find "$d" -type f \
    ! -path '*/__pycache__/*' \
    ! -path '*/.pytest_cache/*' \
    ! -path '*/.ruff_cache/*' \
    ! -path '*/.mypy_cache/*' \
    ! -path '*/node_modules/*' \
    -print
done | sort -u > "$FOCUS_TXT"

TOTAL=$(wc -l < "$FOCUS_TXT" | tr -d ' ')
echo "[INFO] 代碼檔案數 = $TOTAL"
[ "$TOTAL" -gt 0 ] || { echo "[FATAL] 代碼清單為空"; exit 97; }

# 4) 產出 MANIFEST & GIT（顯示進度）
echo -e "path\tsize_bytes\tmtime_iso\tsha256" > "$MANIFEST_TSV"
echo -e "path\ttracked\tfirst_commit_iso\tlast_commit_iso\tcommit_count" > "$GIT_TSV"

i=0
while IFS= read -r f; do
  i=$((i+1))
  [ -f "$f" ] || continue
  size="$(stat -c '%s' -- "$f" 2>/dev/null || echo 0)"
  mt_epoch="$(stat -c '%Y' -- "$f" 2>/dev/null || echo 0)"
  mt_iso="$(date -u -d "@$mt_epoch" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "")"
  sha="$(sha256sum -- "$f" | awk '{print $1}')"
  printf "%s\t%s\t%s\t%s\n" "$f" "$size" "$mt_iso" "$sha" >> "$MANIFEST_TSV"

  if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
    tracked=1
    last_commit_iso="$(git log --follow -1 --format=%ad --date=iso-strict -- "$f" || true)"
    first_commit_iso="$(git log --follow --format=%ad --date=iso-strict -- "$f" | tail -n1 || true)"
    commit_count="$(git rev-list --count HEAD -- "$f" 2>/dev/null || echo 0)"
  else
    tracked=0; first_commit_iso=""; last_commit_iso=""; commit_count=0
  fi
  printf "%s\t%s\t%s\t%s\t%s\n" "$f" "$tracked" "$first_commit_iso" "$last_commit_iso" "$commit_count" >> "$GIT_TSV"

  if (( i % 50 == 0 )); then
    printf "[MANIFEST] %d/%d 完成\r" "$i" "$TOTAL"
  fi
done < "$FOCUS_TXT"
echo; echo "[INFO] MANIFEST 完成：$i/$TOTAL"

# 5) 初步新舊分類（以最後 commit；沒有就用 mtime）
now_epoch="$(date -u +%s)"
echo -e "path\tperiod_tag\tpath_tag" > "$CLASSIFY_TSV"
while IFS=$'\t' read -r path size mtime_iso sha; do
  last_commit_iso="$(awk -F'\t' -v p="$path" '$1==p{print $4}' "$GIT_TSV" | head -n1)"
  ref="${last_commit_iso:-$mtime_iso}"
  re=0; [ -n "$ref" ] && re="$(date -u -d "$ref" +%s 2>/dev/null || echo 0)"
  age=99999; [ "$re" -gt 0 ] && age=$(( (now_epoch - re)/86400 ))
  if   [ "$age" -le 30 ]; then per="CURRENT_30D"
  elif [ "$age" -le 90 ]; then per="RECENT_90D"
  else per="LEGACY_OLD"; fi
  case "$path" in
    *legacy*|*archive*|*.bak*|*_old*|*old/*) ptag="PATH_LEGACY" ;;
    *) ptag="PATH_NORMAL" ;;
  esac
  printf "%s\t%s\t%s\n" "$path" "$per" "$ptag" >> "$CLASSIFY_TSV"
done < <(tail -n +2 "$MANIFEST_TSV")

# 6) 總結（列出每個包含目錄的檔案數）
{
  echo "# Focus Code List Summary"
  echo "root: $ROOT"
  echo "timestamp: $TS"
  echo "code_dirs: ${INCLUDE_DIRS[*]}"
  echo "files_total: $TOTAL"
  echo
  echo "per-dir counts:"
  awk -F/ '{print $1}' "$FOCUS_TXT" | sort | uniq -c | sort -nr
  echo
  echo "outputs:"
  echo "- $FOCUS_TXT"
  echo "- $MANIFEST_TSV"
  echo "- $GIT_TSV"
  echo "- $CLASSIFY_TSV"
} | tee "$SUMMARY_MD"

echo "[DONE] 輸出完成：$OUT"
