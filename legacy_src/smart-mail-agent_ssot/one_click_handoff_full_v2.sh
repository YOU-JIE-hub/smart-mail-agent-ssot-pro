#!/usr/bin/env bash
set -Eeuo pipefail
say(){ echo "[$(date +%H:%M:%S)] $*"; }

ROOT="${PROJ:-$HOME/projects/smart-mail-agent_ssot}"
MAX_MB="${MAX_MB:-2}"          # 單檔 > 此大小(MB) → 輸出同名 .POINTER
SPLIT_MB="${SPLIT_MB:-90}"     # 主 zip > 此大小(MB) → 切片
LIMIT_DIRS="${LIMIT_DIRS:-}"   # 只打包這些子路徑（以逗號分隔），留空=全專案
EXTRA_EXCLUDES="${EXTRA_EXCLUDES:-}"  # 追加排除（逗號分隔，可給相對路徑）

TS="$(date +%Y%m%dT%H%M%S)"
OUT="$ROOT/handoff/$TS"
STAGE="$OUT/stage"
LOG="$OUT/handoff_${TS}.log"
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
  echo "[HINT] 交接輸出與日誌在：$OUT"
  open_path "$OUT" || true
  exit $code
}
trap 'on_err $LINENO' ERR INT

# ---- 進專案 + venv ----
say "enter project & venv → $ROOT"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"
export LC_ALL=C

# ---- 組排除清單（轉成絕對路徑，避免 find -path 比對不到）----
to_abs(){ local p="$1"; [[ "$p" = /* ]] && printf '%s' "$p" || printf '%s/%s' "$ROOT" "$p"; }
DEFAULT_EXCLUDES=( ".git" ".venv" "venv" "node_modules" "__pycache__" ".pytest_cache" ".mypy_cache" "handoff" )
IFS=',' read -r -a EXTRA_ARR <<< "$EXTRA_EXCLUDES"
EXCLUDES=()
for e in "${DEFAULT_EXCLUDES[@]}"; do EXCLUDES+=( "$(to_abs "$e")" ); done
for e in "${EXTRA_ARR[@]}"; do [[ -n "$e" ]] && EXCLUDES+=( "$(to_abs "$e")" ); done

# ---- roots（起點）----
build_roots(){
  if [ -n "$LIMIT_DIRS" ]; then
    IFS=',' read -r -a LROOTS <<< "$LIMIT_DIRS"
    for r in "${LROOTS[@]}"; do
      local abs="$(to_abs "$r")"
      [ -d "$abs" ] && printf '%s\0' "$abs"
    done
  else
    printf '%s\0' "$ROOT"
  fi
}

# ---- 建立 -prune 參數（純陣列，不用 eval）----
build_prune_args(){
  local args=()
  args+=( "(" )
  local first=1
  for ex in "${EXCLUDES[@]}"; do
    [ -z "$ex" ] && continue
    if [ $first -eq 0 ]; then args+=( -o ); fi
    args+=( -path "$ex" )
    first=0
  done
  args+=( ")" -prune -o -type f -print0 )
  printf '%s\0' "${args[@]}"
}

# ---- 取檔案大小（跨平台）----
get_size(){ python3 - "$1" <<'PY'
import os,sys; print(os.path.getsize(sys.argv[1]))
PY
}

# ---- 安全 copy（保留時間戳）----
safe_copy(){ # $1=src $2=dst
  mkdir -p "$(dirname "$2")"
  if command -v install >/dev/null 2>&1; then install -m 0644 "$1" "$2"; else cp -p "$1" "$2"; fi
}

# ---- sha256 ----
sha256_of(){
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    python3 - "$1" <<'PY'
import sys,hashlib
h=hashlib.sha256()
with open(sys.argv[1],'rb') as f:
  for ch in iter(lambda:f.read(1<<20), b''): h.update(ch)
print(h.hexdigest())
PY
  fi
}

# ---- 主掃描（串流 + 進度）----
say "scan files（串流；僅 > ${MAX_MB}MB 轉 .POINTER）"
MAX_BYTES=$((MAX_MB * 1024 * 1024))
COUNT=0 COPIED=0 POINTERS=0 BYTES_TOTAL=0

# 取 prune 陣列
PRUNE_ARGS=()
# 透過 \0 分隔轉回陣列
while IFS= read -r -d '' token; do PRUNE_ARGS+=( "$token" ); done < <(build_prune_args)

# 逐個 root 跑 find
while IFS= read -r -d '' ROOT_CAND; do
  [ ! -d "$ROOT_CAND" ] && continue
  # 直接把陣列展開給 find，完全避免 eval
  find "$ROOT_CAND" "${PRUNE_ARGS[@]}" | while IFS= read -r -d '' ABS; do
    REL="${ABS#$ROOT/}"
    # 續跑支援：已有檔或 .POINTER 則跳過
    if [ -f "$STAGE/$REL" ] || [ -f "$STAGE/$REL.POINTER" ]; then
      COUNT=$((COUNT+1))
      continue
    fi

    SIZE="$(get_size "$ABS")"
    BYTES_TOTAL=$((BYTES_TOTAL + SIZE))

    if (( SIZE > MAX_BYTES )); then
      SHA="$(sha256_of "$ABS")"
      mkdir -p "$STAGE/$(dirname "$REL")"
      {
        echo "# POINTER (file too large)"
        echo "original_rel: $REL"
        echo "size_bytes: $SIZE"
        echo "sha256: $SHA"
        echo "note: 同名指示檔；原檔超過 ${MAX_MB}MB，未收錄於交接包。"
      } > "$STAGE/$REL.POINTER"
      POINTERS=$((POINTERS+1))
    else
      safe_copy "$ABS" "$STAGE/$REL"
      COPIED=$((COPIED+1))
    fi

    COUNT=$((COUNT+1))
    if (( COUNT % 1000 == 0 )); then
      say "progress: scanned=$COUNT  copied=$COPIED  pointers=$POINTERS  bytes_total=$BYTES_TOTAL"
    fi
  done
done < <(build_roots)

# 若沒有任何檔案，直接報明確錯誤，避免 zip 空包
if ! find "$STAGE" -type f -print -quit | grep -q .; then
  echo "[FATAL] 沒有任何檔案被收進 stage/（可能 LIMIT_DIRS/EXCLUDES 設太嚴，或掃描早前中斷）"
  exit 14
fi

say "build checksums (sha256)"
if command -v sha256sum >/dev/null 2>&1; then
  ( cd "$STAGE" && find . -type f -print0 | sort -z | xargs -0 sha256sum ) > "$OUT/sha256.txt"
else
  STAGE="$STAGE" OUT_FILE="$OUT/sha256.txt" python3 - <<'PY'
import os,hashlib
root=os.environ["STAGE"]; out=os.environ["OUT_FILE"]
def sha256(p):
  h=hashlib.sha256()
  with open(p,'rb') as f:
    for ch in iter(lambda:f.read(1<<20),b''): h.update(ch)
  return h.hexdigest()
with open(out,'w') as w:
  for dp,_,fs in os.walk(root):
    for f in sorted(fs):
      p=os.path.join(dp,f); rel=os.path.relpath(p,root)
      w.write(f"{sha256(p)}  ./{rel}\n")
PY
fi

SUMMARY="$OUT/SUMMARY_${TS}.txt"
say "write summary → $SUMMARY"
{
  echo "# Handoff Summary ($TS)"
  echo "- project_root: $ROOT"
  echo "- scanned_files: $COUNT"
  echo "- files_copied: $COPIED"
  echo "- files_pointer: $POINTERS  (單檔 > ${MAX_MB}MB)"
  echo "- total_bytes_scanned: $BYTES_TOTAL"
  echo "- excludes:"
  for e in "${EXCLUDES[@]}"; do echo "  - $e"; done
  [ -n "$LIMIT_DIRS" ] && echo "- limit_dirs: $LIMIT_DIRS" || true
  echo
  echo "## 還原說明"
  echo "指示檔（*.POINTER）紀錄原檔相對路徑、大小與 sha256。"
  echo "依 original_rel 放回原檔後，可用 sha256 驗證完整性。"
} > "$SUMMARY"

ZIP="$OUT/code_${TS}.zip"
say "create zip → $ZIP"
if command -v zip >/dev/null 2>&1; then
  ( cd "$STAGE" && zip -q -9 -r "$ZIP" . )
else
  STAGE="$STAGE" ZIP="$ZIP" python3 - <<'PY'
import zipfile, os
stage=os.environ["STAGE"]; out=os.environ["ZIP"]
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for dp,_,fs in os.walk(stage):
    for f in fs:
      p=os.path.join(dp,f)
      z.write(p, os.path.relpath(p, stage))
PY
fi

SIZE_ZIP=$(stat -c%s "$ZIP" 2>/dev/null || stat -f%z "$ZIP")
SPLIT_BYTES=$((SPLIT_MB * 1024 * 1024))
if (( SIZE_ZIP > SPLIT_BYTES )); then
  say "split zip into ${SPLIT_MB}MB parts"
  split -b "${SPLIT_MB}m" -d -a 2 "$ZIP" "$ZIP.part-"
fi

say "DONE → $OUT"
open_path "$OUT" || true
