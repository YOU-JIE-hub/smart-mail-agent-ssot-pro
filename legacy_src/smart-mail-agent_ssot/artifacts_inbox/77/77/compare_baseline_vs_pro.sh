#!/usr/bin/env bash
set -Eeuo pipefail
b=reports_auto/external_eval_manual.txt
p=reports_auto/external_eval_manual_pro.txt
awk '/accuracy/{print "[BASE]",$0}' "$b"
awk '/accuracy/{print "[PRO ]",$0}' "$p"
python - <<'PY'
import re, pathlib
def acc(p):
    s=pathlib.Path(p).read_text(encoding='utf-8')
    m=re.search(r'accuracy\s+([\d\.]+)', s)
    return float(m.group(1)) if m else None
ba=acc("reports_auto/external_eval_manual.txt")
pa=acc("reports_auto/external_eval_manual_pro.txt")
print(f"[DELTA] pro - base = {pa - ba:+.3f}")
PY
