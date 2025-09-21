#!/usr/bin/env bash
set -Eeuo pipefail

say(){ echo "[$(date +%H:%M:%S)] $*"; }

# ====== 可調參數（可用環境變數覆蓋） ======
ROOT="${PROJ:-$HOME/projects/smart-mail-agent_ssot}"
MAX_MB="${MAX_MB:-2}"            # > 這個大小(單檔，MB) → 不複製，改寫同名 .POINTER
SPLIT_MB="${SPLIT_MB:-90}"       # zip 超過這大小(整包，MB) → 自動切片
LIMIT_DIRS="${LIMIT_DIRS:-}"     # 只打包這些相對路徑，逗號分隔；空字串=整個專案
EXTRA_EXCLUDES="${EXTRA_EXCLUDES:-}" # 追加排除，逗號分隔(支援glob)
OPEN_ON_FAIL="${OPEN_ON_FAIL:-0}"    # 失敗時是否自動開資料夾(0/1)
OPEN_AFTER="${OPEN_AFTER:-1}"        # 成功完成後是否開資料夾(0/1)

TS="$(date +%Y%m%dT%H%M%S)"
OUT="$ROOT/handoff/$TS"
STAGE="$OUT/stage"
LOG="$OUT/handoff_${TS}.log"
ZIP="$OUT/code_${TS}.zip"

mkdir -p "$STAGE"
exec > >(tee -a "$LOG") 2>&1

open_path(){ # $1=path
  local p="$1"
  if grep -qi microsoft /proc/version 2>/dev/null; then
    command -v wslpath >/dev/null 2>&1 && explorer.exe "$(wslpath -w "$p")" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$p" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then open "$p" >/dev/null 2>&1 || true
  fi
}

on_err(){ code=$?; line=$1
  echo "[ERROR] exit=$code line=$line"
  echo "[HINT] 檔案與紀錄都在：$OUT"
  if [ "$OPEN_ON_FAIL" = "1" ]; then open_path "$OUT"; fi
  exit $code
}
trap 'on_err $LINENO' ERR

# ---- 小工具：跨平台 stat/sha256 ----
stat_bytes(){ # $1=file
  if command -v stat >/dev/null 2>&1; then
    # Linux GNU coreutils
    stat -c %s "$1" 2>/dev/null || stat -f %z "$1"
  else
    wc -c < "$1"
  fi
}
sha256_file(){ # $1=file
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'
  fi
}

# ---- 進專案＋啟環境（你要求永遠先做） ----
say "[0] enter project & venv → $ROOT"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

# ---- 準備 include / exclude 清單 ----
IFS=, read -r -a _LIMS <<< "$LIMIT_DIRS"
INCLUDES=()
if [ -n "$LIMIT_DIRS" ]; then
  for d in "${_LIMS[@]}"; do
    d="$(echo "$d" | sed 's#^/*##; s#/*$##')"    # 去頭尾斜線
    [ -d "$ROOT/$d" ] && INCLUDES+=("$d")
  done
else
  INCLUDES+=(".")  # 全專案
fi

# 預設排除（glob）
DEFAULT_EXCLUDES=(
  "*/.git/*" "*/.idea/*" "*/.vscode/*" "*/node_modules/*"
  "*/__pycache__/*" "*/.pytest_cache/*" "*/.mypy_cache/*"
  "handoff/*"  # 避免遞迴吃到自己
)
IFS=, read -r -a _EXTRA <<< "$EXTRA_EXCLUDES"
EXCLUDES=("${DEFAULT_EXCLUDES[@]}")
for e in "${_EXTRA[@]}"; do
  [ -n "$e" ] && EXCLUDES+=("$e")
done

should_exclude(){ # $1=relpath
  local rel="$1"
  for pat in "${EXCLUDES[@]}"; do
    if [[ "$rel" == $pat ]]; then return 0; fi
  done
  return 1
}

MAX_BYTES=$(( MAX_MB * 1024 * 1024 ))
SPLIT_BYTES=$(( SPLIT_MB * 1024 * 1024 ))

say "[1] scan files（串流；僅 > ${MAX_MB}MB 轉 .POINTER）"
TOTAL=0; POINTERS=0; COPIED=0

for base in "${INCLUDES[@]}"; do
  # 用 -print0 防空白/特殊字元；逐檔處理，零 eval
  find "$base" -type f -print0 |
  while IFS= read -r -d '' f; do
    # 絕對/相對處理
    abs="$ROOT/$f"; abs="$(readlink -f "$f" 2>/dev/null || realpath "$f")"
    rel="${abs#$ROOT/}"

    # 排除
    if should_exclude "$rel"; then continue; fi

    dest="$STAGE/$rel"
    mkdir -p "$(dirname "$dest")"

    sz=$(stat_bytes "$abs")
    if [ "$sz" -gt "$MAX_BYTES" ]; then
      sha=$(sha256_file "$abs")
      ptr="${dest}.POINTER"
      {
        echo "# POINTER (large file omitted from handoff)"
        echo "REL: $rel"
        echo "ABS: $abs"
        echo "BYTES: $sz"
        echo "SHA256: $sha"
        echo "GENERATED_AT: $(date -Iseconds)"
        echo "HOW_TO_RESTORE: 將原始大檔放回專案根下的相同 REL 路徑，並比對 SHA256。"
      } > "$ptr"
      POINTERS=$((POINTERS+1))
    else
      # -p 保留時間權限；reflink 可用就用
      cp --reflink=auto -p "$abs" "$dest" 2>/dev/null || cp -p "$abs" "$dest"
      COPIED=$((COPIED+1))
    fi

    TOTAL=$((TOTAL+1))
    if (( TOTAL % 500 == 0 )); then say "  ... processed $TOTAL files"; fi
  done
done

# 若 stage 為空，避免 zip "Nothing to do"：丟一個說明檔
if ! find "$STAGE" -type f -print -quit >/dev/null 2>&1; then
  echo "EMPTY STAGE (檢查 LIMIT_DIRS/EXTRA_EXCLUDES 是否把所有檔案排光了)" > "$STAGE/README.EMPTY"
fi

say "[2] build checksums (sha256)"
{
  find "$STAGE" -type f -print0 | while IFS= read -r -d '' f; do
    rel="${f#$STAGE/}"
    sum=$(sha256_file "$f")
    printf "%s  %s\n" "$sum" "$rel"
  done
} > "$OUT/sha256.txt"

say "[3] write summary → $OUT/SUMMARY_${TS}.txt"
{
  echo "HANDOFF SUMMARY"
  echo "TS: $TS"
  echo "ROOT: $ROOT"
  echo "INCLUDES: ${INCLUDES[*]}"
  echo "EXCLUDES: ${EXCLUDES[*]}"
  echo "MAX_MB: $MAX_MB"
  echo "SPLIT_MB: $SPLIT_MB"
  echo "FILES: total=$TOTAL  copied=$COPIED  pointers=$POINTERS"
} > "$OUT/SUMMARY_${TS}.txt"

say "[4] create zip → $ZIP"
(
  cd "$STAGE"
  zip -q -9 -r "$ZIP" . >/dev/null
)

# 切片（必要時）
ZIP_BYTES=$(stat_bytes "$ZIP")
if [ "$ZIP_BYTES" -gt "$SPLIT_BYTES" ]; then
  say "[5] split zip (${SPLIT_MB}MB per part)"
  split -b "${SPLIT_MB}m" -d -a 2 "$ZIP" "${ZIP}.part-"
  say "[5] done split -> $(ls -1 ${ZIP}.part-* | wc -l) parts"
fi

say "[DONE] out=$OUT  (copied=$COPIED, pointers=$POINTERS)"
if [ "$OPEN_AFTER" = "1" ]; then open_path "$OUT"; fi
