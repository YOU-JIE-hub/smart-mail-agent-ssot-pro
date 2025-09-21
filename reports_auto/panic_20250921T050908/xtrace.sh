+ CMD='PYTHONPATH=. python3 scripts/repair_roles_and_env.py'
+ '[' -z 'PYTHONPATH=. python3 scripts/repair_roles_and_env.py' ']'
+ echo '== SNAPSHOT 20250921T050908 =='
+ pwd
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ grep -E 'INTENT_PKL|SPAM_PKL|PYTHONPATH'
+ env
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc 'PYTHONPATH=. python3 scripts/repair_roles_and_env.py'
++ tee -a reports_auto/panic_20250921T050908/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : PYTHONPATH=. python3 scripts/repair_roles_and_env.py'
+ echo '- LOG  : reports_auto/panic_20250921T050908/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T050908/run.err'
+ echo '- PY   : reports_auto/panic_20250921T050908/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T050908/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T050908/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T050908/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250921T050908/run.err reports_auto/panic_20250921T050908/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T050908/run.err reports_auto/panic_20250921T050908/python_stderr.txt
+ grep -qi 'ModuleNotFoundError: No module named' reports_auto/panic_20250921T050908/run.err reports_auto/panic_20250921T050908/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T050908/run.err reports_auto/panic_20250921T050908/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250921T050908/oom.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T050908/REPORT.md\nreports_auto/panic_20250921T050908/run.log\nreports_auto/panic_20250921T050908/run.err\nreports_auto/panic_20250921T050908/python_stderr.txt\nreports_auto/panic_20250921T050908/xtrace.sh\nreports_auto/panic_20250921T050908/system.txt\nreports_auto/panic_20250921T050908/oom.txt\n'
+ exit 0
