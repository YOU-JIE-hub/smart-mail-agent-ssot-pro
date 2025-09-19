#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[ERR] line:$LINENO cmd:${BASH_COMMAND}"' ERR
say(){ echo "[$(date +%H:%M:%S)] $*"; }

ROOT="${ROOT:-$HOME/projects/smart-mail-agent-ssot-pro}"
cd "$ROOT"; [ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"
export SMA_EMAIL_WHITELIST="${SMA_EMAIL_WHITELIST:-noreply@example.com}"

TS="$(date +%Y%m%dT%H%M%S)"
RUN_DIR="reports_auto/e2e_mail/${TS}"
OUTBOX="${RUN_DIR}/rpa_out/email_outbox"
SENT="${RUN_DIR}/rpa_out/email_sent"
OVR="configs/intent_names_override.txt"

mkdir -p artifacts_prod tools configs "$OUTBOX" "$SENT" reports_auto/status
export RUN_DIR OUTBOX SENT

say "[0] 寫入 6 意圖白名單"
cat > "$OVR" <<'TXT'
一般回覆
報價
投訴
技術支援
規則詢問
資料異動
TXT

say "[1/5] 產生 names.json（以白名單為準）"
python - <<'PY'
from pathlib import Path
import json
names = [l for l in Path("configs/intent_names_override.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
Path("artifacts_prod/intent_names.json").write_text(json.dumps({"names":names}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[OK] names -> artifacts_prod/intent_names.json  N={len(names)}")
PY

say "[2/5] 產生 intent_contract.json（subject_tag=[名稱]）"
python - <<'PY'
from pathlib import Path
import json
names = json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8"))["names"]
intents=[{"name":n, "subject_tag":f"[{n}]", "attachments":[], "inline":None} for n in names]
Path("artifacts_prod/intent_contract.json").write_text(json.dumps({"intents":intents}, ensure_ascii=False, indent=2), encoding="utf-8")
print("[OK] contract -> artifacts_prod/intent_contract.json")
PY

say "[3/5] 種 outbox 稿件並自動批核"
python - <<'PY'
from pathlib import Path
import os, json
outbox = Path(os.environ["OUTBOX"]); outbox.mkdir(parents=True, exist_ok=True)
names = json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8"))["names"]
for n in names:
    p_txt = outbox / f"{n}.txt"; p_apr = outbox / f"{n}.approved"
    if not p_txt.exists(): p_txt.write_text(f"這是 [{n}] 測試郵件。\n", encoding="utf-8")
    if not p_apr.exists(): p_apr.write_text("", encoding="utf-8")
print(f"[SEED] outbox -> {outbox}")
PY

say "[4/5] 合約驅動寄送（SMA_DRY_RUN=1 僅 .eml 落地）"
python - <<'PY'
from pathlib import Path
import os, json
from time import strftime, localtime
run   = Path(os.environ["RUN_DIR"])
sent  = run/"rpa_out/email_sent"; sent.mkdir(parents=True, exist_ok=True)
outb  = run/"rpa_out/email_outbox"
names = json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8"))["names"]
contract = json.loads(Path("artifacts_prod/intent_contract.json").read_text(encoding="utf-8"))
tags = {it["name"]: it.get("subject_tag","") for it in contract.get("intents",[])}
to = os.environ.get("SMA_EMAIL_WHITELIST","noreply@example.com")
dry = os.environ.get("SMA_DRY_RUN","")!=""
for n in names:
    subj = f"{tags.get(n,'')} {n} 測試".strip()
    body = (outb/f"{n}.txt").read_text(encoding="utf-8")
    eml = f"To: {to}\nFrom: noreply@example.com\nSubject: {subj}\nDate: {strftime('%a, %d %b %Y %H:%M:%S %z', localtime())}\nMIME-Version: 1.0\nContent-Type: text/plain; charset=utf-8\n\n{body}\n"
    (sent/f"{n}.eml").write_text(eml, encoding="utf-8")
    print(f"{'[DRY] would send' if dry else '[OK] sent'} {n}.eml -> {to}")
print(f"[DONE] run={run.name}")
PY

say "[5/5] 摘要"
python - <<'PY'
from pathlib import Path
import os, json, re
base=Path("reports_auto/e2e_mail")
runs=sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
run=Path(os.environ.get("RUN_DIR")) if os.environ.get("RUN_DIR") else (runs[0] if runs else None)
outbox=run/"rpa_out/email_outbox"; sent=run/"rpa_out/email_sent"
nj=Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8")
cj=Path("artifacts_prod/intent_contract.json").read_text(encoding="utf-8")
rep=Path(f"reports_auto/status/INTENTS_{run.name}.md")
rep.write_text(f"# Intent Contract (v4 fix)\n- run_dir: {run}\n- outbox: {len(list(outbox.glob('*.txt')))} files\n- sent:   {len(list(sent.glob('*.eml')))} files\n\n## names.json\n{nj}\n\n## contract (head)\n{cj[:2000]}\n", encoding="utf-8")
print(f"[DONE] report -> {rep}")
PY
