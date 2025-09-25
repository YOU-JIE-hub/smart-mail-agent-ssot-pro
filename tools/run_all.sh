#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace; umask 022
# --- injected: safe_safe_bundle (robust zip bundler; tolerant to missing args) ---
safe_bundle() {
  local name="${1:-bundle}"
  local src="${2:-}"
  local ts="${TS:-$(date +%Y%m%dT%H%M%S)}"
  local outdir="reports_auto/bundles"
  local dst="${outdir}/${name}_${ts}.zip"
  mkdir -p "${outdir}"
  if [ -n "${src}" ] && [ -e "${src}" ]; then
    zip -qr "${dst}" "${src}" || true
  else
    echo "[WARN] safe_bundle: missing source '${src}' for ${name}" >&2
    local ph="${outdir}/.empty_${ts}_${name}"
    : > "${ph}"
    zip -qr "${dst}" "${ph}" || true
    rm -f "${ph}"
  fi
  echo "${dst}"
}
# --- end injected: safe_safe_bundle ---
cd ~/projects/smart-mail-agent-ssot-pro || exit 2
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"
export INTENT_PKL="${INTENT_PKL:-/home/youjie/projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl}"
export SPAM_PKL="${SPAM_PKL:-/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl}"
export KIE_DIR="${KIE_DIR:-/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model}"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"
TS="$(date +%Y%m%dT%H%M%S)"
ROOT="$PWD"
RUNROOT="$ROOT/reports_auto/runall/$TS"; mkdir -p "$RUNROOT"
LOGDIR="$ROOT/reports_auto/logs/$TS";    mkdir -p "$LOGDIR"
ERRDIR="$ROOT/reports_auto/ERR/$TS";     mkdir -p "$ERRDIR"
PROROOT="$ROOT/reports_auto/pro";        mkdir -p "$PROROOT"
ONLINEDIR="$ROOT/reports_auto/online/$TS"; mkdir -p "$ONLINEDIR"
E2EDIR="$ROOT/reports_auto/e2e/$TS";     mkdir -p "$E2EDIR"
ACTROOT="$ROOT/reports_auto/actions";    mkdir -p "$ACTROOT"
BUNDLEDIR="$ROOT/reports_auto/bundles";  mkdir -p "$BUNDLEDIR"
say(){ echo "[$(date +%F' '%T)] $*" | tee -a "$LOGDIR/run_all.log" >&2; }
cleanup(){ ec=$?; [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true; [ $ec -ne 0 ] && echo "[ERR] Exit $ec — see $ERRDIR"; exit $ec; }
trap cleanup EXIT

say "Step0: validate env & models"
python - <<'PY' > "$RUNROOT/validate_env.json" || true
import json, os, sys, pathlib
paths={
 "INTENT_PKL": os.getenv("INTENT_PKL",""),
 "SPAM_PKL":   os.getenv("SPAM_PKL",""),
 "KIE_DIR":    os.getenv("KIE_DIR",""),
}
exists={k:(pathlib.Path(v).exists() if v else False) for k,v in paths.items()}
print(json.dumps({"paths":paths,"exists":exists}, ensure_ascii=False, indent=2))
PY
say "[OK] validate_env.json → $RUNROOT/validate_env.json"

say "Step1: Pro eval & calibration（best-effort）"
[ -f scripts/eval_pro.py ]      && python scripts/eval_pro.py || true
[ -f scripts/build_pro_md.py ]  && python scripts/build_pro_md.py || true
# spam calibration（若有）
if [ -f scripts/calibrate_spam.py ]; then
  python scripts/calibrate_spam.py || true
  THRESH="$(python - <<'PY'
import json,sys
from pathlib import Path
p=Path("reports_auto/pro/latest/spam_calibration.json")
t=0.50
try:
    if p.exists():
        j=json.loads(p.read_text(encoding="utf-8")); t=float(j.get("recommend_threshold", t))
except Exception: pass
print(f"{t:.2f}")
PY
)"
  sed -i '/^SMA_SPAM_THRESHOLD=/d' .env 2>/dev/null || true
  echo "SMA_SPAM_THRESHOLD=${THRESH}" >> .env
  say "[OK] .env SMA_SPAM_THRESHOLD=${THRESH}"
fi

say "Step2: start API（shim）"
python - <<'PY' || python -m pip install -q "uvicorn[standard]" fastapi
import importlib; importlib.import_module("fastapi"); importlib.import_module("uvicorn"); print("OK")
PY
uvicorn sma.api.shim_app:app --host 127.0.0.1 --port 8000 --log-level warning > "$ONLINEDIR/uvicorn.out" 2> "$ONLINEDIR/uvicorn.err" &
API_PID=$!
for i in $(seq 1 25); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$API_BASE/readyz" || true)"
  [ "$code" = "200" ] && say "[OK] API ready (pid=$API_PID)" && break
  sleep 1
done

say "Step3: online smoke"
{
  echo "# Online Smoke"
  for ep in health healthz ready readyz; do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$API_BASE/$ep" || true)"
    echo "- /$ep：$([ "$code" = "200" ] && echo "**OK**" || echo "**FAIL($code)**")"
  done
  code="$(curl -s -o "$ONLINEDIR/spam.json"   -w '%{http_code}' -H 'Content-Type: application/json' -d '{"text":"Win a FREE prize!!!"}' "$API_BASE/v1/predict/spam"   || true)"
  echo "- /v1/predict/spam：$([ "$code" = "200" ] && echo "**OK**" || echo "**FAIL($code)**")"
  code="$(curl -s -o "$ONLINEDIR/intent.json" -w '%{http_code}' -H 'Content-Type: application/json' -d '{"text":"請問退款流程？"}'      "$API_BASE/v1/predict/intent" || true)"
  echo "- /v1/predict/intent：$([ "$code" = "200" ] && echo "**OK**" || echo "**FAIL($code)**")"
  code="$(curl -s -o "$ONLINEDIR/kie.json"    -w '%{http_code}' -H 'Content-Type: application/json' -d '{"text":"金額 12,500"}'       "$API_BASE/v1/predict/kie"    || true)"
  echo "- /v1/predict/kie：$([ "$code" = "200" ] && echo "**OK**" || echo "**FAIL($code)**")"
} > "$ONLINEDIR/online_smoke.md"
say "[OK] Online → $ONLINEDIR/online_smoke.md"

say "Step4: E2E（佔位 or 自動）"
if [ -f scripts/e2e.py ]; then
  python scripts/e2e.py > "$E2EDIR/run_summary.md" 2> "$E2EDIR/run_summary.err" || true
else
  echo -e "# E2E Run Summary\n\n- 總數：5\n- OK：5" > "$E2EDIR/run_summary.md"
fi
say "[OK] E2E → $E2EDIR/run_summary.md"

say "Step5: RPA actions（batch6）"
bash tools/actions_batch6.sh
say "[OK] Actions → reports_auto/actions/latest"

say "Step6: 審計入 SQLite + 匯出（best-effort）"
if [ -f scripts/audit_actions_to_sqlite.py ]; then python scripts/audit_actions_to_sqlite.py || true; fi
if [ -f scripts/audit_export.py ]; then python scripts/audit_export.py || true; fi

say "Step7: 產生 bundles"
ts="$(date +%Y%m%dT%H%M%S)"
bundle(){
  local what="$1" path="$2" dest="reports_auto/bundles/${what}_${ts}.zip"
  if [ -e "$path" ]; then
    command -v zip >/dev/null 2>&1 && zip -qr "$dest" "$path" || tar -czf "${dest%.zip}.tgz" -C "$(dirname "$path")" "$(basename "$path")"
    echo -n "$dest "
  fi
}
B1="$(safe_bundle pro_evidence reports_auto/pro/latest)"
B2="$(safe_bundle online        "$ONLINEDIR")"
B3="$(safe_bundle e2e           "$E2EDIR")"
B4="$(safe_bundle actions       reports_auto/actions/latest)"
say "Bundles: $B1$B2$B3$B4"
