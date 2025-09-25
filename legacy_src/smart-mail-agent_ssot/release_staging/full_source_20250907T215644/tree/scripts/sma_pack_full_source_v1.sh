#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="release_staging/${TS}_full_source"
mkdir -p "${OUT}"

# 1) 產生樹狀目錄與忽略清單
IGNORE_FILE="${OUT}/.snapshot_exclude.lst"
cat > "${IGNORE_FILE}" <<'EOF'
^\.git(/|$)
^\.venv(/|$)
^__pycache__(/|$)
^\.mypy_cache(/|$)
^\.pytest_cache(/|$)
^\.ruff_cache(/|$)
^reports_auto/final_dump/.+\.tar\.gz$
^release_staging/.+\.tar\.gz$
^data/.+\.raw(/|$)?
^data/.+\.secrets(/|$)?
^artifacts_prod/.+\.pkl$
EOF

# 2) 清單 + SHA256
MAN="${OUT}/CODE_MANIFEST.md"
echo "# Code Snapshot Manifest (${TS})" > "${MAN}"
echo "" >> "${MAN}"
echo '```' >> "${MAN}"
( printf "Tree (top 2 levels):\n"; find . -maxdepth 2 -type d -print ) >> "${MAN}"
echo '```' >> "${MAN}"
echo "" >> "${MAN}"
echo "| file | bytes | sha256 |" >> "${MAN}"
echo "|---|---:|---|" >> "${MAN}"

# 3) 建 tar.gz（套用忽略規則）
TARBALL="release_staging/full_source_${TS}.tar.gz"
# 準備檔案列表
FILES=$(git ls-files 2>/dev/null || true)
if [ -z "${FILES}" ]; then
  # 若不是 git repo，退回用 find
  FILES=$(find . -type f -not -path "./.git/*")
fi

# 過濾忽略
FILTERED=""
while IFS= read -r f; do
  rel="${f#./}"
  skip=0
  while IFS= read -r rule; do
    [ -z "$rule" ] && continue
    echo "$rel" | grep -Eq "$rule" && { skip=1; break; }
  done < "${IGNORE_FILE}"
  [ $skip -eq 0 ] && FILTERED="${FILTERED}
${rel}"
done <<< "${FILES}"

TMP_LIST="${OUT}/filelist.txt"
printf "%s\n" "${FILTERED}" | sed '/^\s*$/d' | sort -u > "${TMP_LIST}"

# 寫入 manifest
while IFS= read -r f; do
  [ -f "$f" ] || continue
  sz=$(stat -c%s "$f")
  sha=$(sha256sum "$f" | awk '{print $1}')
  echo "| \`$f\` | ${sz} | \`${sha}\` |" >> "${MAN}"
done < "${TMP_LIST}"

# 打包
tar -czf "${TARBALL}" -T "${TMP_LIST}"

echo "[OK] full source tar => ${TARBALL}"
echo "[OK] manifest        => ${MAN}"
