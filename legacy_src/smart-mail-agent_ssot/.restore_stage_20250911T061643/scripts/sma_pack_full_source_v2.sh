#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
TS="$(date +%Y%m%dT%H%M%S)"
OUTDIR="release_staging/full_source_${TS}"
STAGE="${OUTDIR}/tree"
mkdir -p "$STAGE" "release_staging"

log(){ echo "[$(date +%H:%M:%S)] $*"; }

# 需要 rsync
command -v rsync >/dev/null 2>&1 || { echo "[FATAL] rsync 不存在，請先安裝"; exit 2; }

# 只收程式碼/設定/校準等可公開內容，排除大型輸出與敏感資料
INCL="$(mktemp)"
cat > "$INCL" <<'EOF'
+ /scripts/**
+ /src/**
+ /sma/**
+ /rules/**
+ /config/**
+ /docker/**
+ /tests/**
+ /artifacts_prod/**
+ /Makefile
+ /requirements*.txt
+ /pyproject.toml
+ /poetry.lock
+ /Pipfile
+ /Pipfile.lock
+ /setup.cfg
+ /setup.py
+ /.env.example
+ /.envrc
+ /README*
+ /LICENSE*
+ /*.md
# 資料表結構/說明（若有）
+ /db/*.sql
+ /db/README*
# pipeline 分數板（僅 md）
+ /reports_auto/status/*.md
# 其餘全部排除
- *
EOF

log "[STEP] Collecting source files into ${STAGE}/"
rsync -a --prune-empty-dirs --include='*/' --include-from="$INCL" --exclude='*' "$ROOT"/ "$STAGE"/

log "[STEP] Pruning caches"
find "$STAGE" -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.DS_Store' | xargs -r rm -rf

log "[STEP] Writing tree & manifest"
TREEF="${OUTDIR}/tree.txt"
MANI="${OUTDIR}/CODE_MANIFEST.md"
( cd "$STAGE" && { command -v tree >/dev/null 2>&1 && tree -a || find . -type f | sort; } ) > "$TREEF"

echo "# Code Manifest (${TS})" > "$MANI"
echo "" >> "$MANI"
echo "| file | bytes | sha256 |" >> "$MANI"
echo "|---|---:|---|" >> "$MANI"
while IFS= read -r f; do
  [ -f "$f" ] || continue
  sz=$(stat -c%s "$f")
  sha=$(sha256sum "$f" | awk '{print $1}')
  echo "| \`$f\` | $sz | \`$sha\` |" >> "$MANI"
done < <(cd "$STAGE" && find . -type f | sort)

TARBALL="release_staging/full_source_${TS}.tar.gz"
log "[STEP] Packing tarball => ${TARBALL}"
tar -czf "$TARBALL" -C "$OUTDIR" .

log "[DONE] Full source bundle:"
ls -lh "$TARBALL"
echo "MANIFEST: ${MANI}"
echo "TREE:     ${TREEF}"
