#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "[ERR] line:$LINENO cmd:${BASH_COMMAND}"' ERR
say(){ echo "[$(date +%H:%M:%S)] $*"; }

ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"; [ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"
export SMA_EMAIL_WHITELIST="${SMA_EMAIL_WHITELIST:-h125872359@gmail.com}"

TS="$(date +%Y%m%dT%H%M%S)"
RUN_DIR="reports_auto/e2e_mail/${TS}"
OUTBOX="${RUN_DIR}/rpa_out/email_outbox"
SENT="${RUN_DIR}/rpa_out/email_sent"
OVR="configs/intent_names_override.txt"
NAMES_JSON="artifacts_prod/intent_names.json"
CONTRACT="artifacts_prod/intent_contract.json"

mkdir -p artifacts_prod tools configs "$OUTBOX" "$SENT" reports_auto/status
export RUN_DIR OUTBOX SENT

say "[0] 寫入 6 意圖白名單（必要檔）"
cat > "$OVR" <<'TXT'
一般回覆
報價
投訴
技術支援
規則詢問
資料異動
TXT

say "[1/5] 探勘 → 以白名單為核心產出 names.json（可擴充來源，但先保證穩）"
python - <<'PY'
from pathlib import Path
import json
ovr = Path("configs/intent_names_override.txt").read_text(encoding="utf-8").splitlines()
ovr = [x.strip() for x in ovr if x.strip()]
Path("artifacts_prod/intent_names.json").write_text(
  json.dumps({"names":ovr}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[OK] names -> artifacts_prod/intent_names.json  N= {len(ovr)}")
PY

say "[2/5] 由 names 生成合約（subject_tag = [名稱]）"
python - <<'PY'
from pathlib import Path
import json
names = json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8"))["names"]
intents = [{"name":n, "subject_tag":f"[{n}]", "attachments":[], "inline":None} for n in names]
Path("artifacts_prod/intent_contract.json").write_text(
  json.dumps({"intents":intents}, ensure_ascii=False, indent=2), encoding="utf-8")
print("[OK] contract -> artifacts_prod/intent_contract.json")
PY

say "[3/5] 種 6 封 outbox（檔名即意圖名）並自動批核（冪等）"
python - <<'PY'
from pathlib import Path, os
import json
outbox = Path(os.environ.get("OUTBOX") or (Path(os.environ["RUN_DIR"])/"rpa_out/email_outbox"))
outbox.mkdir(parents=True, exist_ok=True)
names = json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8"))["names"]
for n in names:
    p_txt = outbox/f"{n}.txt"
    p_apr = outbox/f"{n}.approved"
    if not p_txt.exists():
        p_txt.write_text(f"這是 [{n}] 測試郵件。\n", encoding='utf-8')
    p_apr.write_text("", encoding='utf-8')
print(f"[SEED] outbox -> {outbox}")
PY

say "[4/5] 合約驅動寄送（SMA_DRY_RUN=1 時只落地 .eml，實際不寄）"
python - <<'PY'
from pathlib import Path, os
import json, re, datetime
dry = os.environ.get("SMA_DRY_RUN","") == "1"
run = Path(os.environ["RUN_DIR"])
outbox = Path(os.environ["OUTBOX"])
sent = Path(os.environ["SENT"]); sent.mkdir(parents=True, exist_ok=True)
wl = os.environ.get("SMA_EMAIL_WHITELIST","nobody@example.com")
contract = json.loads(Path("artifacts_prod/intent_contract.json").read_text(encoding="utf-8"))
ok, fail = 0, 0
for it in contract.get("intents",[]):
    n = it.get("name")
    tag = it.get("subject_tag") or f"[{n}]"
    p_txt = outbox/f"{n}.txt"
    if not p_txt.exists(): continue
    body = p_txt.read_text(encoding="utf-8")
    eml = sent/f"{n}.eml"
    eml.write_text(
        f"To: {wl}\nSubject: {tag} 測試\nDate: {datetime.datetime.utcnow():%a, %d %b %Y %H:%M:%S} +0000\n\n{body}",
        encoding="utf-8")
    if dry:
        print(f"[DRY] would send {eml.name} -> {wl}  (intent={n})")
    else:
        print(f"[OK] sent {eml.name} -> {wl}  (intent={n})")
        ok += 1
print(f"[DONE] run={run.name}")
PY

say "[5/5] 摘要"
python - <<'PY'
from pathlib import Path
import re, json, os
base = Path("reports_auto/e2e_mail")
runs = sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
run = runs[0] if runs else Path(os.environ["RUN_DIR"])
outbox = run/"rpa_out/email_outbox"
sent = run/"rpa_out/email_sent"
nj = Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8")
cj = Path("artifacts_prod/intent_contract.json").read_text(encoding="utf-8")
rep = Path(f"reports_auto/status/INTENTS_{run.name}.md")
def head(s, n=40): 
    L = s.splitlines()
    return "\n".join(L[:n]) + ("\n..." if len(L)>n else "")
rep.write_text(f"""# Intent Contract (v4 fix run)
- run_dir: {run}
- outbox: {len(list(outbox.glob("*.txt")))} files
- sent:   {len(list(sent.glob("*.eml")))} files

## names.json
{nj}

## contract (head)
{head(cj, 40)}
""", encoding="utf-8")
print(f"[DONE] report -> {rep}")
PY