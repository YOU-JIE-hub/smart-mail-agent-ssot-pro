# Panic Report
- Exit code: 0
- CMD  : python3 -m venv .venv 2>/dev/null || true; . .venv/bin/activate; python -m pip install -U pip; if [ -f requirements.txt ]; then pip install -r requirements.txt; else pip install joblib==1.4.2 scikit-learn==1.7.1 "numpy<2.0.0" "pandas>=2" pyyaml>=6; fi
- LOG  : reports_auto/panic_20250921T122428/run.log
- ERR  : reports_auto/panic_20250921T122428/run.err
- PY   : reports_auto/panic_20250921T122428/python_stderr.txt
- OOM  : reports_auto/panic_20250921T122428/oom.txt
- TRACE: reports_auto/panic_20250921T122428/xtrace.sh
- SYS  : reports_auto/panic_20250921T122428/system.txt

## Heuristics
