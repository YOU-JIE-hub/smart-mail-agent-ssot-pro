#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent-ssot-pro}"
cd "$ROOT" || { echo "[ERR] project not found: $ROOT"; exit 1; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

echo "[STEP] Detailed health check..."
python - <<'PY'
from pathlib import Path
import re, json, sys
base=Path("reports_auto/e2e_mail")
runs=sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
if not runs: sys.exit("[HEALTH] no timestamped run under reports_auto/e2e_mail")
run=runs[0]
names=json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8"))["names"]
sent=list((run/"rpa_out/email_sent").glob("*.eml"))
seeds=list((run/"rpa_out/email_outbox").glob("*.txt"))
print(f"[HEALTH] run={run.name} sent={len(sent)} seeds={len(seeds)} names={len(names)}")
if len(sent)!=len(names): sys.exit(f"[HEALTH] sent!=names {len(sent)} vs {len(names)}")
if len(seeds)!=len(names): sys.exit(f"[HEALTH] seeds!=names {len(seeds)} vs {len(names)}")
print("[HEALTH] OK")
PY
