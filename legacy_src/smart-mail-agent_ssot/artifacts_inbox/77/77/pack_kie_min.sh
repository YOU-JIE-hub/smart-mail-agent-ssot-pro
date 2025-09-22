#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

# ------- 1) 鎖定 KIE 模型目錄（優先 SMA_MODEL_DIR，其次 releases/current） -------
if [[ -n "${SMA_MODEL_DIR:-}" && -d "$SMA_MODEL_DIR" ]]; then
  KIE_DIR="$SMA_MODEL_DIR"
elif [[ -d artifacts/releases/kie_xlmr/current ]]; then
  KIE_DIR="artifacts/releases/kie_xlmr/current"
else
  echo "[FATAL] 找不到 KIE 模型目錄（請設 SMA_MODEL_DIR 或建立 artifacts/releases/kie_xlmr/current）"
  exit 90
fi
KIE_REAL="$(readlink -f "$KIE_DIR" || echo "$KIE_DIR")"
echo "[KIE] using model dir: $KIE_REAL"

# ------- 2) 健檢：必要檔與權重 -------
need=(config.json tokenizer.json tokenizer_config.json sentencepiece.bpe.model)
miss=()
for f in "${need[@]}"; do [[ -f "$KIE_REAL/$f" ]] || miss+=("$f"); done
WTS=""
if   [[ -f "$KIE_REAL/model.safetensors" ]]; then WTS="model.safetensors"
elif [[ -f "$KIE_REAL/pytorch_model.bin" ]]; then WTS="pytorch_model.bin"
else miss+=("<weights: model.safetensors|pytorch_model.bin>")
fi
if (( ${#miss[@]} > 0 )); then
  echo "[FATAL] KIE 缺檔：" "${miss[@]}"; exit 91
fi

# ------- 3) 可選：常見的推論/評測腳本（存在就打包，不存在不致命） -------
CAND_SCRIPTS=(
  "sma_tools/_pred_xlmr_snap.py"
  "sma_tools/_eval_occ.py"
  ".sma_tools/_pred_xlmr_snap.py"
  ".sma_tools/_eval_occ.py"
)
EXTRA_SCRIPTS=()
for s in "${CAND_SCRIPTS[@]}"; do
  if [[ -f "$s" ]]; then EXTRA_SCRIPTS+=("$s"); fi
done
for s in sma_tools/snap_decode.py .sma_tools/snap_decode.py; do
  [[ -f "$s" ]] && EXTRA_SCRIPTS+=("$s")
done

# ------- 4) 可選：資料集（存在就一起放，方便 demo） -------
DATASET=()
for d in "data/kie/test_real.jsonl" "data/kie/test.jsonl" "data/kie/valid.jsonl"; do
  [[ -f "$d" ]] && DATASET+=("$d")
done

# ------- 5) 建包工作目錄 -------
TMP="reports_auto/_kie_bundle_tmp"
rm -rf "$TMP"; mkdir -p "$TMP/model"

# 複製模型（整個目錄）
cp -a "$KIE_REAL/." "$TMP/model/"
echo "[COPY] model -> $TMP/model/"

# 複製腳本（如有）
if (( ${#EXTRA_SCRIPTS[@]} > 0 )); then
  mkdir -p "$TMP/tools"
  for s in "${EXTRA_SCRIPTS[@]}"; do
    cp -a "$s" "$TMP/tools/"
    echo "[COPY] tool -> $TMP/tools/$(basename "$s")"
  done
else
  echo "[WARN] 沒找到 _pred_xlmr_snap.py / _eval_occ.py，將提供最小 demo 腳本"
fi

# 複製資料（如有）
if (( ${#DATASET[@]} > 0 )); then
  mkdir -p "$TMP/data/kie"
  for d in "${DATASET[@]}"; do
    cp -a "$d" "$TMP/data/kie/"
    echo "[COPY] data -> $TMP/$(dirname "$d")/$(basename "$d")"
  done
else
  echo "[WARN] 未找到 data/kie/test_real.jsonl（或 test/valid），RUNME 將只做 sanity forward"
fi

# ------- 6) 產出 KIE 模型 dump（結構/標籤/forward） -------
python - <<'PY'
import json, sys
from pathlib import Path
try:
    from transformers import AutoTokenizer, AutoModelForTokenClassification
except Exception as e:
    print("[WARN] transformers 未安裝，略過模型 dump", file=sys.stderr); sys.exit(0)

root = Path("reports_auto/_kie_bundle_tmp")
model = root/"model"
out = root/"kie_model_dump.txt"

tok = AutoTokenizer.from_pretrained(model, use_fast=True)
mdl = AutoModelForTokenClassification.from_pretrained(model)
id2label = mdl.config.id2label if isinstance(mdl.config.id2label, dict) else {}
labels = [id2label.get(str(i), str(i)) for i in range(mdl.num_labels)]
enc = tok("staging 無法登入，2025/08/30；NT$1,200。", return_tensors="pt", truncation=True, max_length=64)
logits = mdl(**enc).logits.shape

out.write_text(
  "# KIE Model Dump\n"
  f"- dir: {model}\n"
  f"- num_labels: {mdl.num_labels}\n"
  f"- labels: {', '.join(labels)}\n"
  f"- forward(logits.shape): {list(logits)}\n",
  encoding="utf-8"
)
print("[OK] wrote", out)
PY

# ------- 7) 生成 RUNME_kie_demo.sh（可重現推論/評測） -------
cat > "$TMP/RUNME_kie_demo.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="$HERE/model"

echo "[INFO] model dir: $MODEL_DIR"
python - <<PY
from pathlib import Path
print(Path("$HERE/kie_model_dump.txt").read_text())
PY

# 若打包中有官方腳本就用；沒有則只做 forward sanity
if [[ -f "$HERE/tools/_pred_xlmr_snap.py" && -f "$HERE/tools/_eval_occ.py" ]]; then
  IN="${1:-$HERE/data/kie/test_real.jsonl}"
  if [[ -f "$IN" ]]; then
    echo "[RUN] pred -> eval on: $IN"
    python "$HERE/tools/_pred_xlmr_snap.py" "$IN" "$MODEL_DIR" "$HERE/kie_preds.jsonl"
    python "$HERE/tools/_eval_occ.py"      "$HERE/kie_preds.jsonl" "$IN" "$HERE/kie_eval.txt"
    sed -n '1,120p' "$HERE/kie_eval.txt"
  else
    echo "[WARN] 找不到測試集（$IN），僅做 forward 檢查"
    python - <<'PY'
from transformers import AutoTokenizer, AutoModelForTokenClassification
from pathlib import Path
d=Path("model")
tok=AutoTokenizer.from_pretrained(d, use_fast=True)
mdl=AutoModelForTokenClassification.from_pretrained(d)
enc=tok("This is a quick sanity forward.", return_tensors="pt")
print("[SANITY] logits", tuple(mdl(**enc).logits.shape))
PY
  fi
else
  echo "[WARN] tools 不齊，僅做 forward 檢查"
  python - <<'PY'
from transformers import AutoTokenizer, AutoModelForTokenClassification
from pathlib import Path
d=Path("model")
tok=AutoTokenizer.from_pretrained(d, use_fast=True)
mdl=AutoModelForTokenClassification.from_pretrained(d)
enc=tok("This is a quick sanity forward.", return_tensors="pt")
print("[SANITY] logits", tuple(mdl(**enc).logits.shape))
PY
fi
SH
chmod +x "$TMP/RUNME_kie_demo.sh"

# ------- 8) 打包 ZIP -------
STAMP="$(date +%Y%m%d-%H%M)"
ZIP="reports_auto/kie_min_bundle_${STAMP}.zip"
( cd "$TMP" && zip -q -r "../kie_min_bundle_${STAMP}.zip" ./* )
echo "[OK] packed -> $ZIP"

# ------- 9) 出示打包清單 -------
echo "[LIST]"
( cd "$TMP" && find . -maxdepth 3 -type f | sed 's,^\./, - ,g' | sort )
