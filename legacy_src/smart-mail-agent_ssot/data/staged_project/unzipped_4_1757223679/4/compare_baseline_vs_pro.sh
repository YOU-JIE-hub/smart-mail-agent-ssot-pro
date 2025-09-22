#!/usr/bin/env bash
set -Eeuo pipefail

# Path to evaluation result files
BASELINE="reports_auto/external_eval_manual.txt"
PRO="reports_auto/external_eval_manual_pro.txt"

# Print Accuracy of Baseline and Pro
awk '/accuracy/{print "[BASE]",$0}' "$BASELINE"
awk '/accuracy/{print "[PRO ]",$0}' "$PRO"

# Python script to calculate the difference between baseline and Pro accuracy
python - <<'PY'
import re
import pathlib

def get_accuracy(file_path):
    content = pathlib.Path(file_path).read_text(encoding='utf-8')
    match = re.search(r'accuracy\s+([\d\.]+)', content)
    return float(match.group(1)) if match else None

base_accuracy = get_accuracy("reports_auto/external_eval_manual.txt")
pro_accuracy = get_accuracy("reports_auto/external_eval_manual_pro.txt")
print(f"[DELTA] Pro - Baseline = {pro_accuracy - base_accuracy:+.3f}")
PY
