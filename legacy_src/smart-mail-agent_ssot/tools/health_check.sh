#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT" || { echo "[ERR] project not found: $ROOT"; exit 1; }
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

echo "[STEP] Detailed health check (with diff)..."
python - <<'PY'
from pathlib import Path
import json, re, sys

names_path = Path("artifacts_prod/intent_names.json")
try:
    names = json.loads(names_path.read_text(encoding="utf-8")).get("names", [])
except FileNotFoundError:
    sys.exit(f"[HEALTH] names file missing: {names_path}")
if not names:
    sys.exit("[HEALTH] names is empty")

base = Path("reports_auto/e2e_mail")
runs = sorted([p for p in base.glob("*") if p.is_dir() and re.fullmatch(r"\d{8}T\d{6}", p.name)], reverse=True)
if not runs:
    sys.exit("[HEALTH] no timestamped run under reports_auto/e2e_mail")
run = runs[0]

sent_dir = run/"rpa_out/email_sent"
outbox   = run/"rpa_out/email_outbox"
sents = list(sent_dir.glob("*.eml"))
seeds = list(outbox.glob("*.txt"))

print(f"[HEALTH] run={run.name} sent={len(sents)} seeds={len(seeds)} names={len(names)}")
if len(sents) != len(names):
    want = set(names)
    have = {p.stem for p in sents}
    missing = sorted(want - have)
    extra   = sorted(have - want)
    print("[HEALTH][DIFF] missing:", missing if missing else "[]")
    print("[HEALTH][DIFF] extra:",   extra if extra else "[]")
    sys.exit(f"[HEALTH] FAIL: sent={len(sents)} names={len(names)} mismatch")
print("[HEALTH] sent == names ==", len(names))
print("[STEP] Quick count assertion...")
assert len(sents) == len(names)
print("[HEALTH] sent == names ==", len(names))
print("[DONE] All checks passed.")
PY
