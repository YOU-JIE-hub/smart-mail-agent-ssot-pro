#!/usr/bin/env bash
set -euo pipefail
TS="$(date +%Y%m%dT%H%M%S)"
OUT="artifacts_prod/env_snapshot_${TS}.txt"
{
  echo "# env snapshot ${TS}"
  python -V
  pip --version
  python - <<'PY'
import platform, sys
print("python:", sys.version.replace("\n"," "))
print("platform:", platform.platform())
PY
  echo ""
  pip freeze
} > "$OUT"
echo "[OK] $OUT"
