#!/usr/bin/env bash
set -Eeuo pipefail

# 讓 Python 找到 src 與 sitecustomize
export PYTHONPATH=".:src"
# 讓所有子行程自動啟動 coverage
export COVERAGE_PROCESS_START="$PWD/.coveragerc"

python - <<'PY'
import sys, subprocess
subprocess.run([sys.executable, "-m", "pip", "install", "-U", "coverage", "coverage-badge", "pytest", "beautifulsoup4"], check=True)
PY

coverage erase
coverage run -m pytest -q
coverage combine
coverage xml -o coverage.xml
coverage report -m
coverage-badge -o assets/badges/coverage.svg -i coverage.xml
echo "完成：assets/badges/coverage.svg"
