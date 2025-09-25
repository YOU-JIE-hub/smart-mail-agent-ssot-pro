#!/usr/bin/env bash
set -Eeuo pipefail
TS="$(date +%Y%m%d_%H%M%S)"
OUTDIR="dist/intent_release_${TS}"
PKG="${OUTDIR}.tar.gz"
mkdir -p "$OUTDIR" reports_auto dist

# 產卡
python -X faulthandler .sma_tools/gen_model_card.py

# 收集交付物
cp -v artifacts/intent_pro_cal.pkl "$OUTDIR"/
cp -v reports_auto/external_eval_manual*.txt "$OUTDIR"/ 2>/dev/null || true
cp -v reports_auto/external_confusion*.tsv "$OUTDIR"/ 2>/dev/null || true
cp -v reports_auto/external_errors*.tsv "$OUTDIR"/ 2>/dev/null || true
cp -v reports_auto/external_fallback_* "$OUTDIR"/ 2>/dev/null || true
cp -v reports_auto/MODEL_CARD.md "$OUTDIR"/
cp -v reports_auto/RELEASE_NOTES.md "$OUTDIR"/
git rev-parse --short HEAD > "$OUTDIR/REV.txt" || echo unknown > "$OUTDIR/REV.txt"

# manifest with sha256
python - <<'PYM'
import hashlib, glob, json, os
outdir=os.environ["OUTDIR"]
files=sorted(glob.glob(outdir+"/*"))
m={os.path.basename(f):{"sha256":hashlib.sha256(open(f,'rb').read()).hexdigest()} for f in files}
open(outdir+"/manifest.json","w").write(json.dumps(m, indent=2))
print("[OK] manifest with", len(m), "files")
PYM

tar -czf "$PKG" -C dist "$(basename "$OUTDIR")"
echo "[PKG] $PKG"

if command -v gh >/dev/null 2>&1; then
  TAG="intent_${TS}"
  gh release create "$TAG" "$PKG" -t "$TAG" -n "INTENT release at $TS"
  echo "[GH] release created: $TAG"
else
  echo "[INFO] gh CLI not found; skip GitHub upload."
fi
