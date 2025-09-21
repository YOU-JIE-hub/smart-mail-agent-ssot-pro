#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo "[ERR] project not found: $ROOT"; exit 1; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || python3 -m venv .venv && . .venv/bin/activate
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

SMA_DRY_RUN=1 bash one_click_patch_intent_contract_all.sh

python - <<'PY'
from pathlib import Path, re, json, sys
base=Path("reports_auto/e2e_mail")
runs=sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
if not runs: sys.exit("no timestamped run found")
run=runs[0]
names=json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8"))["names"]
outbox=run/"rpa_out/email_outbox"; seeds=list(outbox.glob("*.txt"))
rep=Path(f"reports_auto/status/INTENTS_{run.name}.md")
print(f"[SMOKE] run={run.name} seeds={len(seeds)} names={len(names)} summary_exists={rep.exists()}")
if len(seeds)!=len(names) or not rep.exists(): sys.exit(1)
print("[SMOKE] OK")
PY
