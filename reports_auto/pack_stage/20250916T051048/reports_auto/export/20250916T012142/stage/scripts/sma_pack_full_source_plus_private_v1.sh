#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="release_staging/project_snapshot_${TS}"
mkdir -p "${OUT}"

log(){ echo "[$(date +%H:%M:%S)] $*"; }

# 若缺少 v2 腳本，幫你建一份最小可用版
if [ ! -x scripts/sma_pack_full_source_v2.sh ]; then
  echo "[INFO] scripts/sma_pack_full_source_v2.sh 不存在，正在建立..."
  cat > scripts/sma_pack_full_source_v2.sh <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(pwd)"
TS="$(date +%Y%m%dT%H%M%S)"
OUTDIR="release_staging/full_source_${TS}"
STAGE="${OUTDIR}/tree"
mkdir -p "$STAGE" "release_staging"
command -v rsync >/dev/null 2>&1 || { echo "[FATAL] rsync 不存在"; exit 2; }
INCL="$(mktemp)"; cat > "$INCL" <<'EOF'
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
+ /db/*.sql
+ /db/README*
+ /reports_auto/status/*.md
- *
EOF
rsync -a --prune-empty-dirs --include='*/' --include-from="$INCL" --exclude='*' "$ROOT"/ "$STAGE"/
find "$STAGE" -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' -o -name '.DS_Store' | xargs -r rm -rf
TREEF="${OUTDIR}/tree.txt"; MANI="${OUTDIR}/CODE_MANIFEST.md"
( cd "$STAGE" && { command -v tree >/dev/null 2>&1 && tree -a || find . -type f | sort; } ) > "$TREEF"
echo "# Code Manifest (${TS})" > "$MANI"; echo "" >> "$MANI"
echo "| file | bytes | sha256 |" >> "$MANI"; echo "|---|---:|---|" >> "$MANI"
while IFS= read -r f; do [ -f "$f" ] || continue; sz=$(stat -c%s "$f"); sha=$(sha256sum "$f" | awk '{print $1}'); echo "| \`$f\` | $sz | \`$sha\` |" >> "$MANI"; done < <(cd "$STAGE" && find . -type f | sort)
TARBALL="release_staging/full_source_${TS}.tar.gz"; tar -czf "$TARBALL" -C "$OUTDIR" .
echo "$TARBALL"
EOS
  chmod +x scripts/sma_pack_full_source_v2.sh
fi

# 1) 產出完整原始碼包
log "[STEP 1] Building full source bundle"
FULL_SRC_TGZ_PATH="$(bash scripts/sma_pack_full_source_v2.sh | tail -n1 || true)"
# 若上一行只輸出路徑，取最新檔
FULL_SRC_TGZ="$(ls -t release_staging/full_source_*.tar.gz | head -n1)"

# 2) 收集可用的私有/公開/遮罩資料（若存在）
PRIV_TGZ="$(ls -t release_staging/private_bundle_*.tar.gz 2>/dev/null | head -n1 || true)"
PUB_TGZ="$(ls -t release_staging/public_bundle_*.tar.gz  2>/dev/null | head -n1 || true)"
FNDUMP_TGZ="$(ls -t reports_auto/final_dump/final_dump_*.tar.gz 2>/dev/null | head -n1 || true)"

# 3) 摘要說明
cat > "${OUT}/README_SNAPSHOT.md" <<EOF
# Project Snapshot (${TS})

內容：
- full_source.tar.gz           ：完整原始碼（不含大型輸出與私有資料）
- private_bundle_*.tar.gz     ：先前封裝的私有包（若存在）
- public_bundle_*.tar.gz      ：先前封裝的可公開包（若存在）
- final_dump_*.tar.gz         ：最新遮罩資料總包（若存在）
- SNAPSHOT_MANIFEST.md        ：外層清單
EOF

# 4) 收齊到 OUT
cp -f "$FULL_SRC_TGZ" "${OUT}/full_source.tar.gz"
[ -n "${PRIV_TGZ:-}" ] && cp -f "$PRIV_TGZ" "${OUT}/"
[ -n "${PUB_TGZ:-}" ]  && cp -f "$PUB_TGZ"  "${OUT}/"
[ -n "${FNDUMP_TGZ:-}" ] && cp -f "$FNDUMP_TGZ" "${OUT}/"

# 5) 產 SNAPSHOT_MANIFEST
SNAP="${OUT}/SNAPSHOT_MANIFEST.md"
echo "# Snapshot Manifest (${TS})" > "$SNAP"
echo "" >> "$SNAP"
echo "| file | bytes | sha256 |" >> "$SNAP"
echo "|---|---:|---|" >> "$SNAP"
for f in "${OUT}"/*; do
  [ -f "$f" ] || continue
  sz=$(stat -c%s "$f")
  sha=$(sha256sum "$f" | awk '{print $1}')
  echo "| \`$(basename "$f")\` | $sz | \`$sha\` |" >> "$SNAP"
done

# 6) 最外層打包
BIG="release_staging/project_snapshot_${TS}.tar.gz"
tar -czf "$BIG" -C "$(dirname "$OUT")" "$(basename "$OUT")"

log "[DONE] Project snapshot => ${BIG}"
ls -lh "$BIG"
echo "README:  ${OUT}/README_SNAPSHOT.md"
echo "MANI:    ${SNAP}"
