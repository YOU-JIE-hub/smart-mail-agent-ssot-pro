#!/usr/bin/env bash
set -Eeuo pipefail; umask 022
ROOT="${SMA_ROOT:-$HOME/projects/smart-mail-agent}"
cd "$ROOT" || exit 96
RAW="${1:-data/real/inbox.jsonl}"     # 你把真實郵件整理成 {"text":..., "label":可選}
REDACT="data/real/inbox_redacted.jsonl"
SPLIT_DIR="data/real/splits"
LOG_DIR=".sma_logs"; mkdir -p "$LOG_DIR" reports_auto

python sma_tools/redact_text.py "$RAW" "$REDACT"
python sma_tools/split_by_hash.py "$REDACT" "$SPLIT_DIR"

# 用 test 當 gold 的來源，若你有人工金標，覆蓋 data/kie/test.jsonl 再跑
cp -f "$SPLIT_DIR/test.jsonl" data/intent/test.jsonl

# 跑規則 baseline（作為 A 系統）
sma_tools/kie_regex_min.sh data/intent/test.jsonl
cp -f reports_auto/kie_pred.jsonl reports_auto/kie_pred_rule.jsonl

# 跑你的 XLM-R 一鍵（B 系統）——你已經有 sma_kie_xlmr_oneclick.sh
sma_tools/sma_kie_xlmr_oneclick.sh \
  --in-jsonl "$SPLIT_DIR/train.jsonl" \
  --val-jsonl "$SPLIT_DIR/val.jsonl" \
  --gold-jsonl data/kie/test.jsonl \
  --epochs 5 --seed 42

# 產 B 系統的預測（沿用你的一鍵內輸出到 reports_auto/kie_pred.jsonl）
cp -f reports_auto/kie_pred.jsonl reports_auto/kie_pred_model.jsonl

# 95% CI（針對模型 B）
python sma_tools/kie_eval_ci.py reports_auto/kie_pred_model.jsonl data/kie/test.jsonl reports_auto/kie_eval_ci.txt

# 規則 vs 模型 的顯著性
python sma_tools/compare_systems.py \
  reports_auto/kie_pred_rule.jsonl \
  reports_auto/kie_pred_model.jsonl \
  data/kie/test.jsonl \
  reports_auto/kie_model_vs_rule.txt

echo "[REALDATA] onboard complete."
