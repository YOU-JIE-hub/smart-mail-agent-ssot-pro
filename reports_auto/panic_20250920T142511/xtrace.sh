+ CMD='PYTHONPATH=. python3 scripts/smoke_all.py'
+ '[' -z 'PYTHONPATH=. python3 scripts/smoke_all.py' ']'
+ echo '== SNAPSHOT 20250920T142511 =='
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
+ timeout --preserve-status 3h bash -lc 'PYTHONPATH=. python3 scripts/smoke_all.py'
++ tee -a reports_auto/panic_20250920T142511/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : PYTHONPATH=. python3 scripts/smoke_all.py'
+ echo '- LOG  : reports_auto/panic_20250920T142511/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T142511/run.err'
+ echo '- PY   : reports_auto/panic_20250920T142511/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T142511/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T142511/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T142511/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250920T142511/run.err reports_auto/panic_20250920T142511/python_stderr.txt
+ grep -qi 'No module named '\''tools'\''' reports_auto/panic_20250920T142511/run.err reports_auto/panic_20250920T142511/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250920T142511/run.err reports_auto/panic_20250920T142511/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250920T142511/run.err reports_auto/panic_20250920T142511/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T142511/oom.txt
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ printf '%s\n' reports_auto/panic_20250920T142511/REPORT.md reports_auto/panic_20250920T142511/run.log reports_auto/panic_20250920T142511/run.err reports_auto/panic_20250920T142511/python_stderr.txt reports_auto/panic_20250920T142511/xtrace.sh reports_auto/panic_20250920T142511/system.txt reports_auto/panic_20250920T142511/oom.txt
+ echo
+ exit 0
