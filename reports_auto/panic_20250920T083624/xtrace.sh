+ exec
++ tee -a reports_auto/panic_20250920T083624/run.log
++ tee -a reports_auto/panic_20250920T083624/run.err
+ echo '== SNAPSHOT 20250920T083624 =='
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
+ true
+ export PYTHONFAULTHANDLER=1 PYTHONWARNINGS=default PYTHONUNBUFFERED=1 PYTHONHASHSEED=0
+ PYTHONFAULTHANDLER=1
+ PYTHONWARNINGS=default
+ PYTHONUNBUFFERED=1
+ PYTHONHASHSEED=0
+ CMD='python3 scripts/train_binary_safe.py'
+ '[' -z 'python3 scripts/train_binary_safe.py' ']'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc 'python3 scripts/train_binary_safe.py'
++ tee -a reports_auto/panic_20250920T083624/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD: python3 scripts/train_binary_safe.py'
+ echo '- LOG : reports_auto/panic_20250920T083624/run.log'
+ echo '- ERR : reports_auto/panic_20250920T083624/run.err'
+ echo '- PY  : reports_auto/panic_20250920T083624/python_stderr.txt'
+ echo '- OOM : reports_auto/panic_20250920T083624/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T083624/xtrace.sh'
+ echo '- SYS : reports_auto/panic_20250920T083624/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi Killed reports_auto/panic_20250920T083624/run.err reports_auto/panic_20250920T083624/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T083624/oom.txt
+ grep -qi rules_feat reports_auto/panic_20250920T083624/run.err reports_auto/panic_20250920T083624/python_stderr.txt
+ grep -qi 'has .* features, but .* expecting' reports_auto/panic_20250920T083624/run.err reports_auto/panic_20250920T083624/python_stderr.txt
+ grep -qi 'No such file or directory' reports_auto/panic_20250920T083624/run.err reports_auto/panic_20250920T083624/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250920T083624/run.err reports_auto/panic_20250920T083624/python_stderr.txt
+ finish
+ local ec=1
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ echo reports_auto/panic_20250920T083624/REPORT.md
+ echo reports_auto/panic_20250920T083624/run.log
+ echo reports_auto/panic_20250920T083624/run.err
+ echo reports_auto/panic_20250920T083624/python_stderr.txt
+ echo reports_auto/panic_20250920T083624/xtrace.sh
+ echo reports_auto/panic_20250920T083624/system.txt
+ echo reports_auto/panic_20250920T083624/oom.txt
+ echo
+ tee -a reports_auto/panic_20250920T083624/run.log
+ return 1
