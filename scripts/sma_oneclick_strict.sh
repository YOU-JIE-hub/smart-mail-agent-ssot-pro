#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace
ROOT="${ROOT:-/home/youjie/projects/smart-mail-agent-ssot-pro}"; cd "$ROOT"
TS="$(date +%Y%m%dT%H%M%S)"; OUT="reports_auto/oneclick/${TS}"; LOG="$OUT/run.log"; ERR="$OUT/oneclick.err"
mkdir -p "$OUT" reports_auto/.quarantine; exec > >(tee -a "$LOG") 2>&1
trap 'echo "exit_code=$?" > "$ERR"; echo "[ERR] see: $(cd "$OUT"&&pwd)/oneclick.err"; exit 1' ERR
echo "[*] ONECLICK TS=$TS"
GATE="$OUT/gate_scan.txt"
find . -path './.venv' -prune -o -path './reports_auto' -prune -o -type f \( -name '*.py' -o -name '*.sh' \) -print0 | xargs -0 grep -nP '^\s*from\s+pathlib\s+import[^#\n]*\bjson\b' || true | tee "$GATE"
[ -s "$GATE" ] && { echo "[FATAL] bad import → $GATE"; echo "gate=bad_import" > "$ERR"; exit 2; }
scripts/db_migrate.sh
scripts/fix_and_seed_eml.sh
scripts/tri_eval_all.sh || true
scripts/api_down.sh 2>/dev/null || true
scripts/api_up.sh
scripts/api_smoke.sh || true
scripts/sma_healthcheck.sh || true
scripts/retention_gc.sh || true
ln -sfn "$OUT" reports_auto/LATEST || true
echo "[OK] oneclick done → $(cd "$OUT"&&pwd)"
