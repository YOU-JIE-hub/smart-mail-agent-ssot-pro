#!/usr/bin/env bash
set -Eeuo pipefail
REPO_SLUG="${1:-${GITHUB_REPOSITORY:-YOU-JIE-hub/smart-mail-agent}}"
TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
API="https://api.github.com/repos/${REPO_SLUG}/actions/runs?per_page=1"
if [ -z "$TOKEN" ]; then
  echo "[i] 建議先 export GITHUB_TOKEN=你的個人存取權杖（repo scope）以提升 API 額度"
fi
json="$(curl -fsSL -H "Authorization: Bearer ${TOKEN}" -H "X-GitHub-Api-Version: 2022-11-28" "$API")"
python - <<PY
import json,sys,os
j=json.loads(open(0).read())
run=j.get("workflow_runs",[{}])[0]
out={
 "status": run.get("status"),
 "conclusion": run.get("conclusion"),
 "event": run.get("event"),
 "name": run.get("name"),
 "url": run.get("html_url"),
 "created_at": run.get("created_at"),
 "updated_at": run.get("updated_at"),
}
print("\\n".join(f"{k}: {v}" for k,v in out.items()))
PY <<<"$json"
