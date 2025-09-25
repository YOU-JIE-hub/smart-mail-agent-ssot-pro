#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"; cd "$ROOT" || exit 96
WITH_WEIGHTS=0
[ "${1:-}" = "--with-weights" ] && WITH_WEIGHTS=1

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUTDIR="reports_auto/support_bundle_${TS}"
ZIP="reports_auto/support_bundle_${TS}.zip"
mkdir -p "$OUTDIR"

# 0) 來源模型（依序）
KIE_SRC=""
for d in "${SMA_MODEL_DIR:-}" "artifacts/releases/kie_xlmr/current" "artifacts/kie_xlmr"; do
  [ -n "$d" ] && [ -d "$d" ] && { KIE_SRC="$d"; break; }
done

# 1) 收集檔案（不含大權重）
mkdir -p "$OUTDIR"/{logs,reports,scripts,config,data,git,env,models}
# logs & reports
cp -fa .sma_logs/*.log .sma_logs/*.err "$OUTDIR/logs/" 2>/dev/null || true
cp -fa reports_auto/*.txt "$OUTDIR/reports/" 2>/dev/null || true
# scripts（只挑本次用到的）
cp -fa sma_tools/_pred_xlmr_snap.py sma_tools/_eval_occ.py sma_tools/_train_xlmr_quick.py  "$OUTDIR/scripts/" 2>/dev/null || true
cp -fa sma_tools/kie_model_eval_pack.sh sma_tools/kie_robust_safe.sh "$OUTDIR/scripts/" 2>/dev/null || true
# config / rules
cp -fa .sma_tools/ruleset.yml "$OUTDIR/config/" 2>/dev/null || true
# data（只放 gold 與樣本，避免洩漏）
cp -fa data/kie/test_real.jsonl "$OUTDIR/data/" 2>/dev/null || true
# git 狀態
git rev-parse HEAD  > "$OUTDIR/git/commit.txt" 2>/dev/null || true
git status -sb      > "$OUTDIR/git/status.txt" 2>/devnull || true
[ -f .gitattributes ] && cp -fa .gitattributes "$OUTDIR/git/" || true
[ -d .githooks ]     && cp -fa .githooks "$OUTDIR/git/"     || true
# env
python -V                          > "$OUTDIR/env/python.txt" 2>/dev/null || true
pip -V                             >> "$OUTDIR/env/python.txt" 2>/dev/null || true
pip list --format=freeze | sed 's/^/- /' > "$OUTDIR/env/pip-freeze.txt" 2>/dev/null || true

# 2) 模型摘要（不含權重）
if [ -n "$KIE_SRC" ]; then
  REAL="$(readlink -f "$KIE_SRC" || echo "$KIE_SRC")"
  mkdir -p "$OUTDIR/models/kie_xlmr"
  for f in config.json tokenizer.json tokenizer_config.json sentencepiece.bpe.model training_args.bin; do
    [ -f "$REAL/$f" ] && cp -fa "$REAL/$f" "$OUTDIR/models/kie_xlmr/" || true
  done
  # 權重：選擇性打包
  if [ "$WITH_WEIGHTS" -eq 1 ]; then
    if [ -f "$REAL/model.safetensors" ]; then cp -fa "$REAL/model.safetensors" "$OUTDIR/models/kie_xlmr/"; fi
    if [ -f "$REAL/pytorch_model.bin" ]; then cp -fa "$REAL/pytorch_model.bin" "$OUTDIR/models/kie_xlmr/"; fi
  else
    # 沒打包權重就生成 manifest（大小與 sha256）
    python - "$REAL" "$OUTDIR/models/kie_xlmr" <<'PY'
import sys,hashlib,os,json
src, dst = sys.argv[1], sys.argv[2]
def h(p):
    if not os.path.isfile(p): return None
    sha=hashlib.sha256(); 
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20), b""): sha.update(b)
    return {'name':os.path.basename(p),'size':os.path.getsize(p),'sha256':sha.hexdigest()}
items=[]
for w in ("model.safetensors","pytorch_model.bin"):
    p=os.path.join(src,w)
    if os.path.isfile(p): items.append(h(p))
open(os.path.join(dst,"WEIGHTS_MANIFEST.json"),"w",encoding="utf-8").write(json.dumps({'model_dir':src,'weights':items},ensure_ascii=False,indent=2))
PY
  fi
fi

# 3) 產出樹狀與壓縮
( cd "$OUTDIR/.." && zip -qr9 "$(basename "$ZIP")" "$(basename "$OUTDIR")" )
echo "[BUNDLE] -> $ZIP"
echo "[HINT ] 直接把 $ZIP 上傳到聊天視窗即可。"
