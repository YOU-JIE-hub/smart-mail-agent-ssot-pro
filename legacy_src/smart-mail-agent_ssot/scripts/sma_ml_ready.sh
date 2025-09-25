#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1090
source .sma_tools/env_guard.sh
python - <<'PY'
try:
    import sklearn  # noqa: F401
    print("[OK] scikit-learn 已可用")
except Exception:
    print("[INFO] 安裝 scikit-learn …")
    import sys, subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "scikit-learn==1.3.2"])
    print("[OK] scikit-learn 已安裝")
PY
