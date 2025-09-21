#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$(pwd)}"
[ -x "$ROOT/.venv/bin/activate" ] && . "$ROOT/.venv/bin/activate" || true
export PYTHONPATH="$ROOT/src:$ROOT"
export OFFLINE=1

python - <<'PY'
from pprint import pprint
from inference_classifier import classify_intent

samples = [
    ("請問退款流程", "商品有瑕疵，想辦理退貨與退款"),
    ("變更聯絡地址", "需要更新我的電話與地址"),
    ("合作詢問", "想索取報價單並討論合作"),
    ("一般問候", "這是一封沒有關鍵字的測試郵件"),
]
for subj, body in samples:
    res = classify_intent(subj, body)
    print("—"*60)
    print("Subject:", subj)
    print("Body   :", body)
    pprint(res)
PY
echo "[OK] demo 完成。"
