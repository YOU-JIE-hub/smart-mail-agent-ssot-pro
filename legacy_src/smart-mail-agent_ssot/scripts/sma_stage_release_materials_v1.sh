#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
cd "$ROOT"
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

echo "[STEP 0] 產出最新遮罩資料與 SCORECARD"
bash scripts/sma_dump_all_data_masked_v2.sh

TS="$(date +%Y%m%dT%H%M%S)"
STAGE="release_staging/${TS}"
PUB="${STAGE}/public"
PRI="${STAGE}/private"
mkdir -p "${PUB}/docs/public_data/${TS}" "${PUB}/artifacts_prod" "${PUB}/reports" "${PRI}"

LATEST_DUMP="$(ls -td reports_auto/final_dump/*/ 2>/dev/null | head -n1 || true)"
if [ -z "${LATEST_DUMP}" ]; then
  echo "[FATAL] 找不到 reports_auto/final_dump/*/，先跑：bash scripts/sma_dump_all_data_masked_v2.sh"
  exit 2
fi

echo "[STEP 1] 收集 public 素材（遮罩可公開）"
# 遮罩資料
cp -f "${LATEST_DUMP}/intent/intent_dataset_masked.jsonl"             "${PUB}/docs/public_data/${TS}/" 2>/dev/null || true
cp -f "${LATEST_DUMP}/intent/intent_dataset_masked.csv"               "${PUB}/docs/public_data/${TS}/" 2>/dev/null || true
cp -f "${LATEST_DUMP}/kie/gold_merged_mask_fixed.jsonl"               "${PUB}/docs/public_data/${TS}/" 2>/dev/null || true
cp -f "${LATEST_DUMP}/spam/text_predictions_test_masked.tsv"          "${PUB}/docs/public_data/${TS}/" 2>/dev/null || true
# scorecard（若有）
[ -f "${LATEST_DUMP}/SCORECARD_latest.md" ] && cp -f "${LATEST_DUMP}/SCORECARD_latest.md" "${PUB}/docs/" || true
# 各模型最新報告
intent_md="$(ls -t reports_auto/eval/*/metrics_intent_rules_hotfix_v11*.md 2>/dev/null | head -n1 || true)"
kie_md="$(ls -t reports_auto/kie_eval/*/metrics_kie_spans.md           2>/dev/null | head -n1 || true)"
spam_md="$(ls -t reports_auto/eval/*/metrics_spam_autocal_v4.md        2>/dev/null | head -n1 || true)"
[ -n "${intent_md}" ] && cp -f "${intent_md}" "${PUB}/reports/" || true
[ -n "${kie_md}" ]    && cp -f "${kie_md}"    "${PUB}/reports/" || true
[ -n "${spam_md}" ]   && cp -f "${spam_md}"   "${PUB}/reports/" || true
# 校準/門檻（可公開版）
[ -f artifacts_prod/intent_rules_calib_v11c.json ] && cp -f artifacts_prod/intent_rules_calib_v11c.json "${PUB}/artifacts_prod/" || true
[ -f artifacts_prod/ens_thresholds.json ]          && cp -f artifacts_prod/ens_thresholds.json          "${PUB}/artifacts_prod/" || true

echo "[STEP 2] 收集 private 素材（內部回溯）"
# intent 原始/清洗
for f in data/intent_eval/dataset.jsonl data/intent_eval/dataset.cleaned.jsonl data/intent_eval/dataset.cleaned.csv; do
  [ -f "$f" ] && cp -f "$f" "${PRI}/" || true
done
# KIE 原始 gold + 最近 hybrid / unmatched
[ -f data/kie_eval/gold_merged.jsonl ] && cp -f data/kie_eval/gold_merged.jsonl "${PRI}/" || true
latest_kie_dir="$(ls -td reports_auto/kie_eval/*/ 2>/dev/null | head -n1 || true)"
[ -n "${latest_kie_dir}" ] && cp -f "${latest_kie_dir}/hybrid_preds.jsonl" "${PRI}/" 2>/dev/null || true
[ -n "${latest_kie_dir}" ] && cp -f "${latest_kie_dir}/unmatched_examples.jsonl" "${PRI}/" 2>/dev/null || true
# Spam 原始 preds
[ -f artifacts_prod/text_predictions_test.tsv ] && cp -f artifacts_prod/text_predictions_test.tsv "${PRI}/" || true
# Intent 錯分 / FN / FP
latest_eval_dir="$(ls -td reports_auto/eval/*/ 2>/dev/null | head -n1 || true)"
[ -n "${latest_eval_dir}" ] && cp -f "${latest_eval_dir}"/intent_miscls_*.jsonl "${PRI}/" 2>/dev/null || true
[ -n "${latest_eval_dir}" ] && cp -f "${latest_eval_dir}"/FN_*.txt           "${PRI}/" 2>/dev/null || true
[ -n "${latest_eval_dir}" ] && cp -f "${latest_eval_dir}"/FP_*.txt           "${PRI}/" 2>/dev/null || true
# 週期標註包（若有）
latest_label_dir="$(ls -td reports_auto/labeling/*/ 2>/dev/null | head -n1 || true)"
if [ -n "${latest_label_dir}" ]; then
  mkdir -p "${PRI}/labeling"
  rsync -a "${latest_label_dir}" "${PRI}/labeling/" >/dev/null 2>&1 || true
fi

echo "[STEP 3] 產生 MANIFEST 與 INDEX"
python - <<'PY'
# -*- coding: utf-8 -*-
import hashlib, time
from pathlib import Path

ROOT=Path(".")
stages=sorted((ROOT/"release_staging").glob("*/"), key=lambda p:p.stat().st_mtime)
STAGE=stages[-1]
PUB=STAGE/"public"; PRI=STAGE/"private"

def build_manifest(dirpath: Path) -> str:
    rows=[]
    for p in sorted(dirpath.rglob("*")):
        if p.is_file():
            rows.append((p.relative_to(STAGE).as_posix(), p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()))
    out=["# MANIFEST\n","| file | bytes | sha256 |","|---|---:|---|"]
    out += [f"| `{f}` | {sz} | `{h}` |" for f,sz,h in rows]
    return "\n".join(out)+"\n"

(PUB/"MANIFEST_PUBLIC.md").write_text(build_manifest(PUB), encoding="utf-8")
(PRI/"MANIFEST_PRIVATE.md").write_text(build_manifest(PRI), encoding="utf-8")

index = f"""# Release Staging Index ({STAGE.name})

## Public（可公開）
- 遮罩小樣本：`public/docs/public_data/{STAGE.name}/`
- 分數板：`public/docs/SCORECARD_latest.md`（若存在）
- 模型報告：`public/reports/`
- 校準/門檻：`public/artifacts_prod/`
- 清單：`public/MANIFEST_PUBLIC.md`

## Private（內部留存）
- intent 原始/清洗、KIE 原始 gold、最近 hybrid/unmatched、Spam 原始 preds、FN/FP/錯分、（若有）週期標註包
- 清單：`private/MANIFEST_PRIVATE.md`

## 壓縮包將在下一步生成
"""
(STAGE/"INDEX.md").write_text(index, encoding="utf-8")
PY

echo "[STEP 4] 建立 public / private 壓縮包"
tar -C "release_staging/${TS}" -czf "release_staging/public_bundle_${TS}.tar.gz" public
tar -C "release_staging/${TS}" -czf "release_staging/private_bundle_${TS}.tar.gz" private

echo ">>> STAGED at: ${STAGE}"
echo ">>> Quick peek (INDEX.md, first 100 lines):"
sed -n '1,100p' "${STAGE}/INDEX.md" || true
