+ CMD='PYTHONPATH=. python3 scripts/canuse_scan_and_train.py'
+ '[' -z 'PYTHONPATH=. python3 scripts/canuse_scan_and_train.py' ']'
+ echo '== SNAPSHOT 20250920T124259 =='
+ pwd
+ uname -a
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT_PKL|SPAM_PKL|KIE_DIR|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc 'PYTHONPATH=. python3 scripts/canuse_scan_and_train.py'
++ tee -a reports_auto/panic_20250920T124259/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD  : PYTHONPATH=. python3 scripts/canuse_scan_and_train.py'
+ echo '- LOG  : reports_auto/panic_20250920T124259/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T124259/run.err'
+ echo '- PY   : reports_auto/panic_20250920T124259/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T124259/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T124259/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T124259/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250920T124259/run.err reports_auto/panic_20250920T124259/python_stderr.txt
+ grep -qi 'ModuleNotFoundError: No module named '\''tools'\''' reports_auto/panic_20250920T124259/run.err reports_auto/panic_20250920T124259/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250920T124259/run.err reports_auto/panic_20250920T124259/python_stderr.txt
+ grep -qi 'No such file or directory' reports_auto/panic_20250920T124259/run.err reports_auto/panic_20250920T124259/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250920T124259/run.err reports_auto/panic_20250920T124259/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T124259/oom.txt
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ echo reports_auto/panic_20250920T124259/REPORT.md
+ echo reports_auto/panic_20250920T124259/python_stderr.txt
+ echo reports_auto/panic_20250920T124259/run.err
+ echo reports_auto/panic_20250920T124259/run.log
+ echo reports_auto/panic_20250920T124259/xtrace.sh
+ echo reports_auto/panic_20250920T124259/system.txt
+ echo reports_auto/panic_20250920T124259/oom.txt
+ echo
+ exit 1
