#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"; cd "$ROOT" || { echo "[FATAL] repo not found: $ROOT"; exit 96; }
[ -f .venv/bin/activate ] && source .venv/bin/activate 2>/dev/null || true
export HF_HOME="$ROOT/.hf_cache" TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOG=".sma_logs/package_all_${TS}.log"; ERR=".sma_logs/package_all_${TS}.err"
exec > >(tee -a "$LOG") 2> >(tee -a "$ERR" >&2)

sha256() { (command -v sha256sum >/dev/null && sha256sum "$1" | awk '{print $1}') || shasum -a 256 "$1" | awk '{print $1}'; }

echo "[ENV] $(python -V || python3 -V)  OFFLINE=${TRANSFORMERS_OFFLINE:-}  HF_HOME=${HF_HOME:-}"

# -------------------------------------------------------------------
# 0) 依賴（缺才裝，安靜）
python - <<'PY' 2>/dev/null || python -m pip install -q --disable-pip-version-check accelerate sacremoses "protobuf>=3.20.3,<5" sentencepiece >/dev/null 2>&1 || true
import pkgutil,sys
need={"accelerate","sacremoses","sentencepiece","protobuf"}
missing=[m for m in need if pkgutil.find_loader(m) is None]
raise SystemExit(1 if missing else 0)
PY

# -------------------------------------------------------------------
# 1) 定位 KIE 模型 → 健檢 → 建立 release 與 current 連結
KIE_SRC=""
for d in "${SMA_MODEL_DIR:-}" "artifacts/releases/kie_xlmr/current" "artifacts/kie_xlmr"; do
  [ -n "$d" ] && [ -e "$d" ] && { KIE_SRC="$d"; break; }
done
[ -z "$KIE_SRC" ] && { echo "[WARN] no KIE model found. (skip KIE packaging)"; }

KIE_REL=""
if [ -n "$KIE_SRC" ]; then
  [ -L "$KIE_SRC" ] && KIE_REAL="$(readlink -f "$KIE_SRC")" || KIE_REAL="$KIE_SRC"
  echo "[KIE] source = $KIE_REAL"
  # 健檢（檔案齊全 + forward + BIO）
  python - "$KIE_REAL" <<'PY'
import sys, json
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForTokenClassification
d = Path(sys.argv[1])
need = ["config.json","tokenizer.json","tokenizer_config.json","sentencepiece.bpe.model"]
wts = d/"model.safetensors"
if not wts.exists(): wts = d/"pytorch_model.bin"
missing = [p for p in need if not (d/p).is_file()] + ([] if wts.exists() else ["weights"])
if missing: 
    print(json.dumps({"ok":False,"dir":str(d),"missing":missing},ensure_ascii=False)); sys.exit(2)
tok = AutoTokenizer.from_pretrained(d, use_fast=True)
mdl = AutoModelForTokenClassification.from_pretrained(d)
labs = set(mdl.config.id2label.values()) if isinstance(mdl.config.id2label,dict) else set()
must = {"B-amount","I-amount","B-date_time","I-date_time","B-env","I-env"}
miss = sorted(must - labs)
if miss:
    print(json.dumps({"ok":False,"dir":str(d),"missing_labels":miss},ensure_ascii=False)); sys.exit(3)
enc = tok("staging 無法登入，2025/08/30；NT$1,200。", return_tensors="pt", truncation=True, max_length=128)
out = mdl(**enc).logits.shape
print(json.dumps({"ok":True,"dir":str(d),"logits":list(out)},ensure_ascii=False))
PY
  # 建立 release 版本（若 source 不在 releases 之下就複製過去；排除 checkpoint-*）
  if [[ "$KIE_REAL" != "$ROOT/artifacts/releases/kie_xlmr/"* ]]; then
    KIE_REL="artifacts/releases/kie_xlmr/kie_xlmr"
    mkdir -p "$KIE_REL"
    rsync -a --delete --exclude 'checkpoint-*' "$KIE_REAL"/ "$KIE_REL"/
  else
    # 已經是 releases 內：直接用
    KIE_REL="$KIE_REAL"
  fi
  ln -sfn "$(readlink -f "$KIE_REL")" artifacts/releases/kie_xlmr/current
  echo "[KIE] current -> $(readlink -f artifacts/releases/kie_xlmr/current)"
fi

# -------------------------------------------------------------------
# 2) 定位 INTENT 模型（*.pkl）→ 打包 release → current 連結
INT_REL=""
if [ ! -e "artifacts/releases/intent/current" ]; then
  mapfile -t INT_CAND < <(find artifacts -maxdepth 1 -type f -name "intent_*.pkl" 2>/dev/null | sort -r)
  if ((${#INT_CAND[@]})); then
    TS2="$(date -u +%Y%m%dT%H%M%SZ)"
    INT_REL="artifacts/releases/intent/${TS2}-intent-pro"
    mkdir -p "$INT_REL"
    cp -v "${INT_CAND[0]}" "$INT_REL"/ 2>/dev/null || true
    for j in artifacts/intent*_labels*.json artifacts/intent_labels*.json; do
      [ -f "$j" ] && cp -v "$j" "$INT_REL/"
    done
    # manifest
    python - "$INT_REL" <<'PY'
import sys, json, hashlib
from pathlib import Path
rel=Path(sys.argv[1]); items=[]
for p in rel.iterdir():
    if p.is_file():
        h=hashlib.sha256()
        with p.open("rb") as f:
            for b in iter(lambda:f.read(1<<20), b""): h.update(b)
        items.append({"file":p.name,"size":p.stat().st_size,"sha256":h.hexdigest()})
(rel/"manifest.json").write_text(json.dumps({"path":str(rel),"files":items},ensure_ascii=False,indent=2),encoding="utf-8")
print("[INTENT] manifest:", rel/"manifest.json")
PY
    ln -sfn "$(readlink -f "$INT_REL")" artifacts/releases/intent/current
    echo "[INTENT] current -> $(readlink -f artifacts/releases/intent/current)"
  else
    echo "[INTENT] no artifacts/intent_*.pkl found — skip."
  fi
else
  INT_REL="$(readlink -f artifacts/releases/intent/current || true)"
  echo "[INTENT] current -> $INT_REL"
fi

# -------------------------------------------------------------------
# 3) 收集資料與腳本到 release_code/ 與 release_data/
REL_CODE="artifacts/releases/release_code_${TS}"
REL_DATA="artifacts/releases/release_data_${TS}"
mkdir -p "$REL_CODE" "$REL_DATA"

# KIE 相關腳本（存在才複製）
for p in sma_tools/_pred_xlmr_snap.py sma_tools/_eval_occ.py sma_tools/_train_xlmr_quick.py sma_tools/pos_oversample.py sma_tools/ensemble_regex_model.py sma_tools/kie_model_eval_pack.sh sma_tools/kie_regex_min.sh; do
  [ -f "$p" ] && cp -v "$p" "$REL_CODE/" || true
done
# INTENT 相關腳本（存在才複製）
for p in .sma_tools/oneclick_train_eval_pro.sh .sma_tools/pro_fallback_threshold.py .sma_tools/compare_baseline_vs_pro.sh sma_tools/run_and_log.sh; do
  [ -f "$p" ] && cp -v "$p" "$REL_CODE/" || true
done
# 規則與模型卡
[ -f .sma_tools/ruleset.yml ] && cp -v .sma_tools/ruleset.yml "$REL_CODE/" || true
[ -f reports_auto/model_card_kie.md ] && cp -v reports_auto/model_card_kie.md "$REL_CODE/" || true
[ -f reports_auto/model_card_pro.md ] && cp -v reports_auto/model_card_pro.md "$REL_CODE/" || true

# 資料（存在才複製）
for d in \
  data/kie/test_real.jsonl \
  data/intent/i_20250901_merged.jsonl \
  data/intent/external_realistic_test.clean.jsonl \
  data/intent/train_aug.jsonl \
  data/intent/val_aug.jsonl \
  data/intent/test.jsonl \
  data/real/inbox.jsonl ; do
  [ -f "$d" ] && install -D -m 0644 "$d" "$REL_DATA/${d#data/}" || true
done

# 報表（存在才複製）
for r in \
  reports_auto/kie_eval_current_snap.txt \
  reports_auto/kie_eval_release_snap.txt \
  reports_auto/kie_fields_ens.txt \
  reports_auto/external_eval_manual_pro.txt \
  reports_auto/external_fallback_eval.txt \
  reports_auto/_confusion_pro.tsv \
  reports_auto/_errors_pro.tsv \
  reports_auto/external_fallback_confusion.tsv \
  reports_auto/external_fallback_errors.tsv ; do
  [ -f "$r" ] && cp -v "$r" "$REL_DATA/" || true
done

# -------------------------------------------------------------------
# 4) 若有 KIE 測試集，就跑一次 snap 解碼評測（用 current）
if [ -f "data/kie/test_real.jsonl" ] && [ -e "artifacts/releases/kie_xlmr/current" ] && [ -f sma_tools/_pred_xlmr_snap.py ] && [ -f sma_tools/_eval_occ.py ]; then
  python sma_tools/_pred_xlmr_snap.py data/kie/test_real.jsonl artifacts/releases/kie_xlmr/current reports_auto/kie_pred_release_snap.jsonl
  python sma_tools/_eval_occ.py        reports_auto/kie_pred_release_snap.jsonl data/kie/test_real.jsonl reports_auto/kie_eval_release_snap.txt
  echo "[EVAL] KIE snap -> reports_auto/kie_eval_release_snap.txt"
fi

# -------------------------------------------------------------------
# 5) 總結（把目前能找到的指標彙總到 reports_auto/release_summary.txt）
SUM="reports_auto/release_summary.txt"; : > "$SUM"
{
  echo "# Release Summary (${TS})"
  echo
  echo "## KIE"
  if [ -f reports_auto/kie_eval_release_snap.txt ]; then
    grep -E "strict_span_[PRF]1=" -n reports_auto/kie_eval_release_snap.txt | sed 's/^/- /'
  elif [ -f reports_auto/kie_eval_current_snap.txt ]; then
    grep -E "strict_span_[PRF]1=" -n reports_auto/kie_eval_current_snap.txt | sed 's/^/- /'
  else
    echo "- (no KIE eval found)"
  fi
  echo
  echo "## INTENT (external)"
  if [ -f reports_auto/external_eval_manual_pro.txt ]; then
    awk 'NR<=30' reports_auto/external_eval_manual_pro.txt
  else
    echo "- (no intent external eval found)"
  fi
} >> "$SUM"
echo "[SUMMARY] -> $SUM"

# -------------------------------------------------------------------
# 6) 建立 ZIP 封裝
BUNDLE="reports_auto/release_bundle_${TS}.zip"
to_zip=()
[ -n "$KIE_REL" ] && to_zip+=("$KIE_REL")
[ -e artifacts/releases/kie_xlmr/current ] && to_zip+=("artifacts/releases/kie_xlmr/current")
[ -e artifacts/releases/intent/current ] && to_zip+=("artifacts/releases/intent/current")
to_zip+=("$REL_CODE" "$REL_DATA" "reports_auto/kie_eval_release_snap.txt" "$SUM")
if command -v zip >/dev/null 2>&1; then
  rm -f "$BUNDLE"; zip -rq "$BUNDLE" "${to_zip[@]}" 2>/dev/null || true
else
  BUNDLE="reports_auto/release_bundle_${TS}.tar.gz"
  tar -czf "$BUNDLE" "${to_zip[@]}" 2>/dev/null || true
fi
echo "[BUNDLE] -> $BUNDLE"

# -------------------------------------------------------------------
# 7) Git LFS 追蹤與提交（不強制 push）
git lfs install || true
grep -q "artifacts/releases/kie_xlmr" .gitattributes 2>/dev/null || cat >> .gitattributes <<EOF
artifacts/releases/kie_xlmr/**/model.safetensors filter=lfs diff=lfs merge=lfs -text
artifacts/releases/kie_xlmr/**/pytorch_model.bin filter=lfs diff=lfs merge=lfs -text
artifacts/releases/kie_xlmr/**/tokenizer.json filter=lfs diff=lfs merge=lfs -text
artifacts/releases/kie_xlmr/**/sentencepiece.bpe.model filter=lfs diff=lfs merge=lfs -text
EOF
grep -q "artifacts/releases/intent" .gitattributes 2>/dev/null || cat >> .gitattributes <<EOF
artifacts/releases/intent/**.pkl filter=lfs diff=lfs merge=lfs -text
artifacts/releases/intent/**.json filter=lfs diff=lfs merge=lfs -text
EOF

git add .gitattributes 2>/dev/null || true
[ -n "$KIE_REL" ] && git add "$KIE_REL" artifacts/releases/kie_xlmr/current 2>/dev/null || true
[ -n "$INT_REL" ] && git add "$INT_REL" artifacts/releases/intent/current 2>/dev/null || true
git add "$REL_CODE" "$REL_DATA" "$BUNDLE" "$SUM" 2>/dev/null || true

F1="$(grep -m1 -Eo "strict_span_F1=([0-9]+\.[0-9]+)" reports_auto/kie_eval_release_snap.txt 2>/dev/null | cut -d= -f2 || true)"
[ -z "$F1" ] && F1="$(grep -m1 -Eo "strict_span_F1=([0-9]+\.[0-9]+)" reports_auto/kie_eval_current_snap.txt 2>/dev/null | cut -d= -f2 || true)"
MSG="Package models & code"
[ -n "$F1" ] && MSG="$MSG — KIE strict F1=${F1}"
git commit -m "$MSG" || true

echo
echo "===== DONE ====="
echo "[LOG] $LOG"
echo "[ERR] $ERR"
echo "[BUNDLE] $BUNDLE"
echo "[TIP] To push:  git remote -v || git remote add origin <URL> ;  git push -u origin HEAD"
