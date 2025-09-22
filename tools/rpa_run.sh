#!/usr/bin/env bash
set -euo pipefail
cd ~/projects/smart-mail-agent-ssot-pro
[ -f .venv/bin/activate ] || python3 -m venv .venv
. .venv/bin/activate
export PYTHONNOUSERSITE=1 PYTHONPATH="$PWD:${PYTHONPATH:-}"
export INTENT_PKL="$HOME/projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl"
export SPAM_PKL="$HOME/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl"
export KIE_DIR="$HOME/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model"
bash tools/panic.sh '. .venv/bin/activate; python3 scripts/validate_env.py'
bash tools/panic.sh '. .venv/bin/activate; python3 scripts/eval_pro.py'
bash tools/panic.sh '. .venv/bin/activate; python3 scripts/build_pro_md.py'
TS=$(date +%Y%m%dT%H%M%S)
OUT="reports_auto/bundles/pro_evidence_${TS}.zip"
mkdir -p reports_auto/bundles
if [ -d reports_auto/pro/latest ]; then
  ( cd reports_auto/pro/latest && zip -qry "../../bundles/$(basename "$OUT")" . )
else
  # 後備：尋找最近一次 pro_*
  LAST=$(ls -td reports_auto/pro/pro_* 2>/dev/null | head -n1 || true)
  [ -n "$LAST" ] && ( cd "$LAST" && zip -qry "../../bundles/$(basename "$OUT")" . )
fi
[ -f "$OUT" ] && sha256sum "$OUT" > "${OUT}.sha256" || true
echo "[RPA DONE]" "$OUT"
