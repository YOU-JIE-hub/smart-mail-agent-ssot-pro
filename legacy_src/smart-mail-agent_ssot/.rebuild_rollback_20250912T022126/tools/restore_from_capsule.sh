#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ZIP_INPUT="${1:-}"
MODE="${2:-soft}"  # soft | hard
LOGDIR="$ROOT/reports_auto/logs"; mkdir -p "$LOGDIR"
STAGEDIR="$ROOT/reports_auto/restores/stage_$(date +%Y%m%dT%H%M%S)"
OUTREPORT="$ROOT/reports_auto/restores/placeholders_report_$(date +%Y%m%dT%H%M%S).txt"
SNAPDIR="$ROOT/reports_auto/restore_snapshots"; mkdir -p "$SNAPDIR"
TS="$(date +%Y%m%dT%H%M%S)"
LOG="$LOGDIR/restore_capsule_${TS}.log"
ERR="$LOGDIR/restore_capsule_${TS}.err"

exec > >(tee "$LOG") 2> >(tee "$ERR" >&2)

echo "[RESTORE] start @ $TS"
echo "[ARGS] ZIP_INPUT=$ZIP_INPUT"
echo "[ARGS] MODE=$MODE"

if [ -z "$ZIP_INPUT" ] || [ ! -f "$ZIP_INPUT" ]; then
  echo "[FATAL] ZIP file not found: $ZIP_INPUT"
  exit 2
fi

# 0) 快照現在專案（防呆）
echo "[STEP 0] snapshot current project -> $SNAPDIR/snapshot_${TS}.tar.gz"
tar -czf "$SNAPDIR/snapshot_${TS}.tar.gz" \
  --exclude "./.venv" --exclude "./.git" --exclude "./node_modules" \
  --exclude "./reports_auto/exports" --exclude "./reports_auto/restore_snapshots" \
  --exclude "./reports_auto/restores" --exclude "./reports_auto/logs" \
  .

# 1) 解壓到 staging
echo "[STEP 1] extract capsule -> $STAGEDIR"
mkdir -p "$STAGEDIR"
python - "$ZIP_INPUT" "$STAGEDIR" <<'PY'
import sys, os, zipfile, tarfile, shutil
src = sys.argv[1]; out = sys.argv[2]
os.makedirs(out, exist_ok=True)
lower = src.lower()
if lower.endswith('.zip'):
    with zipfile.ZipFile(src) as z:
        z.extractall(out)
elif lower.endswith('.tar.gz') or lower.endswith('.tgz') or lower.endswith('.tar'):
    mode = 'r:gz' if lower.endswith(('.tar.gz','.tgz')) else 'r:'
    with tarfile.open(src, mode) as t:
        t.extractall(out)
else:
    print(f"[FATAL] unsupported archive: {src}", file=sys.stderr)
    sys.exit(3)
# 若內有 stage.zip，再解一次
stage_zip = os.path.join(out, 'stage.zip')
if os.path.isfile(stage_zip):
    with zipfile.ZipFile(stage_zip) as z:
        z.extractall(out)
# 若解壓後出現單一最上層資料夾，攤平
entries = [e for e in os.listdir(out) if e not in ('stage.zip',)]
if len(entries)==1 and os.path.isdir(os.path.join(out, entries[0])):
    top = os.path.join(out, entries[0])
    for name in os.listdir(top):
        shutil.move(os.path.join(top, name), os.path.join(out, name))
    os.rmdir(top)
print("[OK] extracted")
PY

# 2) 產生指示檔清單
echo "[STEP 2] scan placeholders -> $OUTREPORT"
PH_CNT=0
{
  echo "# Placeholder Report"
  echo "generated @ $TS"
  echo
  while IFS= read -r -d '' f; do
    if head -n1 "$f" | grep -q '^\[PLACEHOLDER\]'; then
      rel="${f#"$STAGEDIR/"}"
      sz=$(wc -c < "$f" 2>/dev/null || echo 0)
      echo "$rel (size=$sz bytes)"
      PH_CNT=$((PH_CNT+1))
    fi
  done < <(find "$STAGEDIR" -type f -print0)
  echo
  echo "TOTAL_PLACEHOLDERS=$PH_CNT"
} > "$OUTREPORT"
echo "  placeholders: $PH_CNT"

# 3) 覆蓋到專案
echo "[STEP 3] apply to project: mode=$MODE"
# 保護名單（不會刪）
PROTECT=( "./.venv" "./.git" "./node_modules" "./reports_auto" )
if [ "$MODE" = "hard" ]; then
  echo "  - HARD mode: deleting files not in capsule (with protection list)"
  # 列出 staging 中的相對路徑
  mapfile -t want < <( (cd "$STAGEDIR" && find . -type f -print | sed 's|^\./||') )
  # 將當前專案檔相對路徑列出來
  while IFS= read -r -d '' f; do
    rel="${f#./}"
    # 跳過保護名單
    skip=0; for p in "${PROTECT[@]}"; do [[ "./$rel" == "$p"* ]] && { skip=1; break; }; done
    [ $skip -eq 1 ] && continue
    # staging 沒有這個檔 → 刪除
    if ! printf '%s\0' "${want[@]}" | grep -Fzx -- "$rel" >/dev/null 2>&1; then
      rm -f -- "$rel"
      echo "  - rm $rel"
    fi
  done < <(find . -type f -print0)
fi

# 複製/覆蓋（保留權限/時間）
rsync -a "$STAGEDIR"/ ./ 2>&1 | sed 's/^/  rsync: /' || true
echo "[APPLY] done"

# 4) 基本 sanity：Python 語法 & make -n
echo "[STEP 4] sanity checks"
python - <<'PY' || echo "[WARN] python compile errors"
import sys, pathlib, py_compile
root = pathlib.Path('.').resolve()
err = 0
for rel in ('scripts','src'):
    p = root/rel
    if p.exists():
        for f in p.rglob('*.py'):
            try:
                py_compile.compile(str(f), doraise=True)
            except Exception as e:
                print('[PYERR]', f, e)
                err = 1
sys.exit(err)
PY
( make -n >/dev/null ) || echo "[WARN] make parse had issues"

echo "[DONE] restored from capsule. logs at $LOG"
