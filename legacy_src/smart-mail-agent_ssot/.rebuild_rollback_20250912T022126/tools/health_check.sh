#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo "[ERR] project not found: $ROOT"; exit 1; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

echo "[STEP] Detailed health check (with diff)..."
python - <<'PY'
from pathlib import Path, re
import json, sys
names = json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8")).get("names",[])
base = Path("reports_auto/e2e_mail")
runs = sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
if not runs: sys.exit("[HEALTH] no timestamped run under reports_auto/e2e_mail")
run = runs[0]
outbox = run/"rpa_out/email_outbox"
sent   = run/"rpa_out/email_sent"
seeds = list(outbox.glob("*.txt"))
sentm = list(sent.glob("*.eml"))
print(f"[HEALTH] run={run.name} sent={len(sentm)} seeds={len(seeds)} names={len(names)}")
if len(sentm) != len(names): sys.exit(f"[HEALTH] sent != names")
if len(seeds) != len(names): sys.exit(f"[HEALTH] seeds != names")
print("[HEALTH] sent == names == seeds ==", len(names))
PY

echo "[STEP] Quick count assertion..."
python - <<'PY'
from pathlib import Path, re, json
base=Path("reports_auto/e2e_mail")
runs=sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
run=runs[0]
sent=sum(1 for _ in (run/"rpa_out/email_sent").glob("*.eml"))
names=len(json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8"))["names"])
assert sent==names, f"sent={sent} names={names} mismatch"
print("[HEALTH] sent == names ==", names)
print("[DONE] All checks passed.")
PY
