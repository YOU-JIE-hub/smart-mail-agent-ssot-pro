+ exec
++ tee -a reports_auto/panic_20250920T082447/run.log
++ tee -a reports_auto/panic_20250920T082447/run.err
+ echo '== SNAPSHOT 20250920T082447 =='
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
+ export PYTHONFAULTHANDLER=1 PYTHONWARNINGS=default PYTHONUNBUFFERED=1 PYTHONHASHSEED=0
+ PYTHONFAULTHANDLER=1
+ PYTHONWARNINGS=default
+ PYTHONUNBUFFERED=1
+ PYTHONHASHSEED=0
+ CMD='python3 scripts/canuse_scan_and_train.py'
+ '[' -z 'python3 scripts/canuse_scan_and_train.py' ']'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc 'python3 scripts/canuse_scan_and_train.py'
++ tee -a reports_auto/panic_20250920T082447/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD: python3 scripts/canuse_scan_and_train.py'
+ echo '- LOG : reports_auto/panic_20250920T082447/run.log'
+ echo '- ERR : reports_auto/panic_20250920T082447/run.err'
+ echo '- PY  : reports_auto/panic_20250920T082447/python_stderr.txt'
+ echo '- OOM : reports_auto/panic_20250920T082447/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T082447/xtrace.sh'
+ echo '- SYS : reports_auto/panic_20250920T082447/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi Killed reports_auto/panic_20250920T082447/run.err reports_auto/panic_20250920T082447/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T082447/oom.txt
+ grep -qi rules_feat reports_auto/panic_20250920T082447/run.err reports_auto/panic_20250920T082447/python_stderr.txt
+ grep -qi 'has .* features, but .* expecting' reports_auto/panic_20250920T082447/run.err reports_auto/panic_20250920T082447/python_stderr.txt
+ grep -qi 'No such file or directory' reports_auto/panic_20250920T082447/run.err reports_auto/panic_20250920T082447/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250920T082447/run.err reports_auto/panic_20250920T082447/python_stderr.txt
+ finish
+ local ec=1
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ echo reports_auto/panic_20250920T082447/REPORT.md
+ echo reports_auto/panic_20250920T082447/run.log
+ echo reports_auto/panic_20250920T082447/run.err
+ echo reports_auto/panic_20250920T082447/python_stderr.txt
+ echo reports_auto/panic_20250920T082447/xtrace.sh
+ echo reports_auto/panic_20250920T082447/system.txt
+ echo reports_auto/panic_20250920T082447/oom.txt
+ echo
+ tee -a reports_auto/panic_20250920T082447/run.log
+ return 1
