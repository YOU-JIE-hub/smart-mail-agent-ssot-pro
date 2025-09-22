#!/usr/bin/env bash
set -Eeuo pipefail
# 允許位置參數指定輸入；預設用 data/intent/train.jsonl
IN="${1:-data/intent/train.jsonl}"
SILV="data/kie/silver.jsonl"
PRED="reports_auto/kie_pred.jsonl"

mkdir -p "$(dirname "$SILV")" "$(dirname "$PRED")"

# 用環境變數把 IN 傳進 Python（避免 here-doc 展開問題）
INFILE="$IN" python - <<'PY'
import os, re, json, sys
IN   = os.environ.get("INFILE", "data/intent/train.jsonl")
SILV = "data/kie/silver.jsonl"
PRED = "reports_auto/kie_pred.jsonl"

# 先檢查輸入檔是否存在，並統計行數
try:
    with open(IN, "r", encoding="utf-8") as f:
        lines = f.readlines()
except FileNotFoundError:
    print(f"[FATAL] input not found: {IN}", file=sys.stderr)
    sys.exit(91)

pat_amount = re.compile(r"(?:NT\$|USD|\$)\s?\d[\d,]*(?:\.\d+)?")
pat_date   = re.compile(r"(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}/\d{1,2})")
pat_env    = re.compile(r"\b(prod|production|staging|stage|test|dev)\b", re.I)

def spans(t, rx, lab):
    return [{"start": m.start(), "end": m.end(), "label": lab} for m in rx.finditer(t)]

def dump(out_path):
    n = 0
    with open(out_path, "w", encoding="utf-8") as fo:
        for ln in lines:
            o = json.loads(ln)
            t = o.get("text") or ""
            s = []
            s += spans(t, pat_amount, "amount")
            s += spans(t, pat_date,   "date_time")
            s += spans(t, pat_env,    "env")
            fo.write(json.dumps({"text": t, "spans": s}, ensure_ascii=False) + "\n")
            n += 1
    return n

n1 = dump(SILV)
n2 = dump(PRED)
print(f"[INFO] IN={IN} lines={len(lines)}")
print(f"[OK] SILVER {n1} -> {SILV}")
print(f"[OK] PRED   {n2} -> {PRED}")
PY

echo "[DONE] 正則KIE完成：$PRED"
