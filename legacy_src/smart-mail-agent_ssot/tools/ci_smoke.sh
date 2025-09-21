#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo "[ERR] project not found: $ROOT"; exit 1; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || python3 -m venv .venv && . .venv/bin/activate
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

# 守門：壞匯入直接 fail
bash tools/guard_bad_imports.sh

# 產生最新 run（預設不寄信）
: "${SMA_DRY_RUN:=1}"
SMA_DRY_RUN="$SMA_DRY_RUN" bash one_click_patch_intent_contract_all.sh

# 驗證：seeds==names 且摘要存在
python - <<'PY'
from pathlib import Path
import re, json, sys

names = json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8")).get("names", [])
if not names:
    sys.exit("[SMOKE] names is empty")
base  = Path("reports_auto/e2e_mail")
runs  = sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
if not runs: sys.exit("[SMOKE] no timestamped run found")
run   = runs[0]

outbox = run / "rpa_out/email_outbox"
seeds  = list(outbox.glob("*.txt"))
rep    = Path(f"reports_auto/status/INTENTS_{run.name}.md")
print(f"[SMOKE] run={run.name} seeds={len(seeds)} names={len(names)} summary_exists={rep.exists()}")
assert len(seeds) == len(names), f"seeds={len(seeds)} names={len(names)} mismatch"
assert rep.exists(), f"summary missing: {rep}"
print("[SMOKE] OK")
PY
