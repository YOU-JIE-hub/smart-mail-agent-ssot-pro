#!/usr/bin/env bash
set -Eeuo pipefail
set -o errtrace
export PS4='+ [${BASH_SOURCE##*/}:${LINENO}] ► '
trap 'rc=$?; echo "[TRAP][ERR] line=$LINENO rc=$rc cmd=${BASH_COMMAND}"; exit $rc' ERR
trap 'echo "[TRAP][EXIT] rc=$?"' EXIT

PROJ="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$PROJ" || { echo "[ERR] project not found: $PROJ"; exit 90; }

TS="$(date +%F_%H%M%S)"
BASE="smart-mail-agent_${TS}"

# 選擇壓縮器（依序：zstd→pigz→gzip→無壓縮）
COMP="none"; TAR_EXT="tar"
if command -v zstd >/dev/null 2>&1; then
  COMP="zstd"; TAR_EXT="tar.zst"
elif command -v pigz >/dev/null 2>&1; then
  COMP="pigz"; TAR_EXT="tar.gz"
elif command -v gzip >/dev/null 2>&1; then
  COMP="gzip"; TAR_EXT="tar.gz"
else
  echo "[WARN] no compressor (zstd/pigz/gzip). Using uncompressed tar."
fi
echo "[INFO] compressor=${COMP}"

mkdir -p reports_auto .sma_tools

# Summary 檔
echo "[STEP] write reports_auto/PROJECT_SUMMARY.txt"
cat > reports_auto/PROJECT_SUMMARY.txt <<'TXT'
# Smart Mail Agent — Snapshot & Worklog
(此檔由 make_snapshot_10.sh 生成；包含狀態、修補點與下一步。)
TXT

# 專案樹大小
echo "[STEP] write reports_auto/PROJECT_TREE_SIZES.txt"
if du -ah --max-depth=2 . >/dev/null 2>&1; then
  du -ah --max-depth=2 . | sort -h > reports_auto/PROJECT_TREE_SIZES.txt
else
  find . -type f -printf '%s %p\n' 2>/dev/null | sort -n > reports_auto/PROJECT_TREE_SIZES.txt || true
fi

# 打包（排除大檔與暫存）
ARCHIVE="${BASE}.${TAR_EXT}"
echo "[STEP] tar -> ${ARCHIVE}"
EXCLUDES=(
  --exclude-vcs
  --exclude='./.venv'
  --exclude='./artifacts'
  --exclude='./downloads'
  --exclude='./data/*'
  --exclude='./.sma_tools/logs'
  --exclude='./__pycache__'
  --exclude='./*.tar*'
  --exclude='./*.zst*'
)
if [ "$COMP" = "zstd" ]; then
  tar -I zstd -cf "${ARCHIVE}" "${EXCLUDES[@]}" .
elif [ "$COMP" = "pigz" ]; then
  tar --use-compress-program=pigz -cf "${ARCHIVE}" "${EXCLUDES[@]}" .
elif [ "$COMP" = "gzip" ]; then
  tar -zcf "${ARCHIVE}" "${EXCLUDES[@]}" .
else
  tar -cf "${ARCHIVE}" "${EXCLUDES[@]}" .
fi

# 校驗
SUMFILE="${ARCHIVE}.sha256"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${ARCHIVE}" > "${SUMFILE}"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${ARCHIVE}" > "${SUMFILE}"
else
  echo "[WARN] no sha256 tool; skip checksum"; SUMFILE=""
fi

# 切成 10 份（你的 split 支援 -n，若不支援會 fallback）
echo "[STEP] split into 10 parts"
if split -n 10 -d -a 2 --additional-suffix=".part" "${ARCHIVE}" "${BASE}.p" 2>/dev/null; then
  :
else
  echo "[INFO] fallback to byte-based split"
  SZ=$(stat -c%s "${ARCHIVE}" 2>/dev/null || stat -f%z "${ARCHIVE}")
  CHUNK=$(( (SZ + 9) / 10 ))
  split -b "${CHUNK}" -d -a 2 --additional-suffix=".part" "${ARCHIVE}" "${BASE}.p"
fi

echo "[OK] parts:"
ls -lh "${BASE}.p"??.part | sed 's/^/- /'
[ -n "${SUMFILE}" ] && echo "- ${SUMFILE}"

cat <<'NOTE'

# 重新組裝：
cat smart-mail-agent_*.tar.*.p?? > ALL.tar.any
# 驗證（若有校驗檔）：
sha256sum -c smart-mail-agent_*.sha256 2>/dev/null \
 || shasum -a 256 -c smart-mail-agent_*.sha256 2>/dev/null || true
# 解壓：
#   .tar.zst ：tar -I zstd -xf ALL.tar.any
#   .tar.gz  ：tar -zxf ALL.tar.any
#   .tar     ：tar -xf ALL.tar.any
NOTE
