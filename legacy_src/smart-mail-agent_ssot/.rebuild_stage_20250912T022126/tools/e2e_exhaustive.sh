#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"
cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"
OUT="reports_auto/e2e_full/${TS}"
mkdir -p "$OUT"

python - <<'PY'
import json, time, os
from pathlib import Path
from tools.pipeline_baseline import run_pipeline

ROOT = Path(os.environ.get("ROOT") or Path.cwd())
ts   = time.strftime("%Y%m%dT%H%M%S")
cases = [json.loads(s) for s in (ROOT/"fixtures/e2e_inbox.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
rows=[]
for i, ex in enumerate(cases, 1):
    email = ex["email"]
    got = run_pipeline(email, ts)
    rows.append({"i":i,"label": ex.get("label_intent"), "pred": got["intent"], "actions":[a["type"] for a in got["actions"]]})
(Path(f"reports_auto/e2e_full/{ts}/RESULTS.json")).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"[E2E] cases={len(rows)} -> reports_auto/e2e_full/{ts}/RESULTS.json")
PY
echo "[DONE] E2E -> $OUT"
