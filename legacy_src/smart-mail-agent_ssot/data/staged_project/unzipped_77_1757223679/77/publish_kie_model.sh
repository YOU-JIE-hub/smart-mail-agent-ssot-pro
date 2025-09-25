#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
ROOT="${SMA_ROOT:-$PWD}"; cd "$ROOT" || exit 96

# ---- args ----
MODEL_DIR="artifacts/kie_xlmr"
DEST="hf"                       # hf | lfs
HF_REPO="${HF_REPO:-youjie/sma-kie-xlmr}"   # 目標 HF repo（可覆寫）
MIN_F1="${MIN_F1:-0.78}"        # Gate 門檻（用 ensemble 指標）
VER="$(date +%Y%m%d-%H%M)_kie-xlmr_snapc"   # 版本號（可覆寫）
while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL_DIR="$2"; shift 2;;
    --to)    DEST="$2"; shift 2;;
    --ver)   VER="$2"; shift 2;;
    --min-f1) MIN_F1="$2"; shift 2;;
    --hf-repo) HF_REPO="$2"; shift 2;;
    *) echo "[WARN] unknown arg: $1"; shift;;
  esac
done

# ---- sanity: 必要文件 ----
[ -s "$MODEL_DIR/config.json" ] || { echo "[FATAL] missing $MODEL_DIR/config.json"; exit 91; }
[ -s "$MODEL_DIR/model.safetensors" ] || { echo "[FATAL] missing $MODEL_DIR/model.safetensors"; exit 92; }
[ -s "reports_auto/kie_eval_ens.txt" ] || { echo "[FATAL] missing reports_auto/kie_eval_ens.txt"; exit 93; }
[ -s ".sma_tools/ruleset.yml" ] || echo "[WARN] missing .sma_tools/ruleset.yml (not fatal)"

# ---- gating: 讀取 F1 ----
F1=$(awk -F= '/strict_span_F1=/{print $2; exit}' reports_auto/kie_eval_ens.txt)
F1="${F1:-0}"
awk -v f="$F1" -v m="$MIN_F1" 'BEGIN{ if (f+0 < m+0) { printf("[GATE] F1=%.4f < MIN_F1=%.4f\n", f,m); exit 1 } }' || exit 97
printf "[GATE] OK strict_span_F1=%.4f >= %.2f\n" "$F1" "$MIN_F1"

# ---- freeze: 複製模型與指標到版本目錄 ----
OUT="artifacts/releases/kie_xlmr/$VER"; rm -rf "$OUT"; mkdir -p "$OUT/reports.snapshot"
cp -a "$MODEL_DIR/"* "$OUT/"
cp -f reports_auto/kie_eval_*.txt "$OUT/reports.snapshot/" 2>/dev/null || true
cp -f reports_auto/kie_fields_*.txt "$OUT/reports.snapshot/" 2>/dev/null || true
cp -f reports_auto/model_card_kie.md "$OUT/reports.snapshot/" 2>/dev/null || true
# 記錄資料/規則 SHA
sha() { [ -s "$1" ] && (sha256sum "$1" 2>/dev/null || shasum -a256 "$1") | awk '{print $1}' || echo "NA"; }
python - <<PY
import json,glob,os,datetime
snap={
 "version":"$VER",
 "created_utc": datetime.datetime.utcnow().isoformat()+"Z",
 "model_dir":"$MODEL_DIR",
 "files": sorted([os.path.basename(x) for x in glob.glob("$OUT/*")]),
 "data_sha":{
   "test_real":open("data/kie/test_real.jsonl","rb").read(0) and "$(
     sha data/kie/test_real.jsonl
   )" if os.path.exists("data/kie/test_real.jsonl") else "NA",
   "ruleset": "$(
     sha .sma_tools/ruleset.yml
   )" if os.path.exists(".sma_tools/ruleset.yml") else "NA"
 },
 "metrics_file":"reports_auto/kie_eval_ens.txt",
 "strict_span_F1": $F1
}
open("$OUT/RELEASE.json","w",encoding="utf-8").write(json.dumps(snap,ensure_ascii=False,indent=2))
print("[FREEZE] ->", "$OUT")
PY

# ---- 發佈：HF 或 Git LFS ----
if [ "$DEST" = "hf" ]; then
  [ -n "$HF_TOKEN" ] || { echo "[FATAL] export HF_TOKEN=xxx first"; exit 98; }
  python - <<PY
from huggingface_hub import HfApi, create_repo, upload_folder
import os, json
repo_id=os.environ.get("HF_REPO","$HF_REPO")
api=HfApi()
try:
    create_repo(repo_id, private=False, exist_ok=True)
except Exception as e:
    print("[INFO] repo exists or created:", e)
# 上傳整個版本資料夾，revision 用 version tag
upload_folder(
    repo_id=repo_id,
    folder_path="$OUT",
    path_in_repo="$VER",
    commit_message=f"publish $VER (F1=$F1)",
)
print("[HF] uploaded to", repo_id, "at", "$VER")
PY
  echo "[DONE] HF publish -> $HF_REPO / $VER"
elif [ "$DEST" = "lfs" ]; then
  # 確保 LFS 設定與追蹤
  git lfs install 1>/dev/null
  if ! grep -q "safetensors" .gitattributes 2>/dev/null; then
    cat >> .gitattributes <<'G'
artifacts/releases/**/model.safetensors filter=lfs diff=lfs merge=lfs -text
artifacts/releases/**/pytorch_model.bin filter=lfs diff=lfs merge=lfs -text
artifacts/releases/**/tokenizer.json filter=lfs diff=lfs merge=lfs -text
G
    git add .gitattributes
  fi
  git add "$OUT"
  git commit -m "release: $VER (F1=$F1)" || true
  echo "[LFS] committed. Run: git push origin HEAD"
else
  echo "[INFO] skip remote publish (DEST=$DEST). Frozen at $OUT"
fi
