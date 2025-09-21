+ CMD='python3 -m venv .venv 2>/dev/null || true; . .venv/bin/activate; python -m pip install -U pip; if [ -f requirements.txt ]; then pip install -r requirements.txt; else pip install joblib==1.4.2 scikit-learn==1.7.1 "numpy<2.0.0" "pandas>=2" pyyaml>=6; fi'
+ '[' -z 'python3 -m venv .venv 2>/dev/null || true; . .venv/bin/activate; python -m pip install -U pip; if [ -f requirements.txt ]; then pip install -r requirements.txt; else pip install joblib==1.4.2 scikit-learn==1.7.1 "numpy<2.0.0" "pandas>=2" pyyaml>=6; fi' ']'
+ echo '== SNAPSHOT 20250921T122428 =='
+ pwd
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT|SPAM|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc 'python3 -m venv .venv 2>/dev/null || true; . .venv/bin/activate; python -m pip install -U pip; if [ -f requirements.txt ]; then pip install -r requirements.txt; else pip install joblib==1.4.2 scikit-learn==1.7.1 "numpy<2.0.0" "pandas>=2" pyyaml>=6; fi'
++ tee -a reports_auto/panic_20250921T122428/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : python3 -m venv .venv 2>/dev/null || true; . .venv/bin/activate; python -m pip install -U pip; if [ -f requirements.txt ]; then pip install -r requirements.txt; else pip install joblib==1.4.2 scikit-learn==1.7.1 "numpy<2.0.0" "pandas>=2" pyyaml>=6; fi'
+ echo '- LOG  : reports_auto/panic_20250921T122428/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T122428/run.err'
+ echo '- PY   : reports_auto/panic_20250921T122428/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T122428/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T122428/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T122428/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T122428/run.err reports_auto/panic_20250921T122428/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T122428/run.err reports_auto/panic_20250921T122428/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T122428/run.err reports_auto/panic_20250921T122428/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T122428/run.err reports_auto/panic_20250921T122428/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T122428/REPORT.md\nreports_auto/panic_20250921T122428/run.log\nreports_auto/panic_20250921T122428/run.err\nreports_auto/panic_20250921T122428/python_stderr.txt\nreports_auto/panic_20250921T122428/xtrace.sh\nreports_auto/panic_20250921T122428/system.txt\nreports_auto/panic_20250921T122428/oom.txt\n'
+ exit 0
