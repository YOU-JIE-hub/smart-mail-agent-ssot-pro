#!/usr/bin/env bash
set -Eeo pipefail
ROOT="$HOME/projects/smart-mail-agent-ssot-pro"; cd "$ROOT"
PORT="${PORT:-8088}"
python - <<'PY'
import json, urllib.request, os, re
base=f"http://127.0.0.1:{os.environ.get('PORT','8088')}"
def post(p, d):
    r=urllib.request.Request(base+p, data=json.dumps(d).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=12).read().decode())

text="請幫我報價 120000 元，數量 3 台，單號 AB-99127，謝謝！"
cl_rule = post("/classify", {"texts":[text], "route":"rule"})
cl_ml   = post("/classify", {"texts":[text], "route":"ml"})
ext     = post("/extract", {"text": text})

slots = ext.get("slots") or {}

def fill_missing(slots, text):
    s = dict(slots)
    # 價格：同時支援「$120,000」「NTD 120000」「120000 元」
    if s.get("price") in (None,"",0):
        m = (re.search(r'(?:\$|NTD?\s*)\s*([0-9][\d,\.]*)', text, re.I) or
             re.search(r'([0-9][\d,\.]*)\s*(?:元|NTD?|\$)', text, re.I))
        if m: s["price"] = m.group(1).replace(",","")
    # 數量
    if s.get("qty") in (None,"",0):
        m = re.search(r'(?:數量|各|共|x)\s*([0-9]+)', text, re.I)
        if m: s["qty"] = int(m.group(1))
    # 單號/ID
    if s.get("id") in (None,""):
        m = re.search(r'\b([A-Z]{2,}-?\d{4,})\b', text)
        if m: s["id"] = m.group(1)
    return s

slots2 = fill_missing(slots, text)

print("=== DEMO INPUT ===")
print(text)
print("\n=== INTENT ===")
print("rule:", cl_rule)
print("ml  :", cl_ml)
print("\n=== EXTRACT ===")
print("api :", slots)
print("demo:", slots2)
PY
echo "[OK] e2e_smoke on $PORT"
