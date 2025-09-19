#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"

STAGE_TS="${STAGE_TS:-$(ls -td release_staging/*/ | head -n1 | xargs -I{} basename {} || true)}"
[ -n "$STAGE_TS" ] || { echo "[FATAL] no release_staging/*/ found"; exit 2; }

SRC="release_staging/${STAGE_TS}/public"
DEST="docs/releases/${STAGE_TS}"
mkdir -p "$DEST"

echo "[INFO] stage: $SRC -> $DEST"
rsync -a --delete "$SRC/" "$DEST/"

# 更新 docs/releases/INDEX.md
mkdir -p docs/releases
IDX="docs/releases/INDEX.md"
touch "$IDX"
if ! grep -q "$STAGE_TS" "$IDX"; then
  {
    echo "- ${STAGE_TS}"
    echo "  - [Scorecard](./${STAGE_TS}/docs/SCORECARD_latest.md)"
    echo "  - [Reports](./${STAGE_TS}/reports/)"
    echo "  - [Public data](./${STAGE_TS}/docs/public_data/${STAGE_TS}/)"
    echo ""
  } >> "$IDX"
fi

if [ "${PUSH:-0}" = "1" ]; then
  git add docs/releases
  git commit -m "publish public materials ${STAGE_TS}" || true
  git tag -a "pub-${STAGE_TS}" -m "public release ${STAGE_TS}" || true
  git push --follow-tags || true
  echo "[OK] pushed with tag pub-${STAGE_TS}"
else
  echo "[OK] prepared at ${DEST} (dry run, no push)."
  echo "要推送：PUSH=1 bash scripts/sma_publish_public_to_github_v1.sh"
fi
