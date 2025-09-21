+ CMD='PYTHONPATH=. python3 scripts/refind_data_strict.py'
+ '[' -z 'PYTHONPATH=. python3 scripts/refind_data_strict.py' ']'
+ echo '== SNAPSHOT 20250921T081821 =='
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
+ timeout --preserve-status 3h bash -lc 'PYTHONPATH=. python3 scripts/refind_data_strict.py'
++ tee -a reports_auto/panic_20250921T081821/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : PYTHONPATH=. python3 scripts/refind_data_strict.py'
+ echo '- LOG  : reports_auto/panic_20250921T081821/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T081821/run.err'
+ echo '- PY   : reports_auto/panic_20250921T081821/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T081821/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T081821/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T081821/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T081821/run.err reports_auto/panic_20250921T081821/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T081821/run.err reports_auto/panic_20250921T081821/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T081821/run.err reports_auto/panic_20250921T081821/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T081821/run.err reports_auto/panic_20250921T081821/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T081821/REPORT.md\nreports_auto/panic_20250921T081821/run.log\nreports_auto/panic_20250921T081821/run.err\nreports_auto/panic_20250921T081821/python_stderr.txt\nreports_auto/panic_20250921T081821/xtrace.sh\nreports_auto/panic_20250921T081821/system.txt\nreports_auto/panic_20250921T081821/oom.txt\n'
+ exit 0
