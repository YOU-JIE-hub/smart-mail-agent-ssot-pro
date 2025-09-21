+ CMD='python3 - <<'\''PY'\''
print(1/0)
PY'
+ '[' -z 'python3 - <<'\''PY'\''
print(1/0)
PY' ']'
+ echo '== SNAPSHOT 20250920T140813 =='
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
+ timeout --preserve-status 3h bash -lc 'python3 - <<'\''PY'\''
print(1/0)
PY'
++ tee -a reports_auto/panic_20250920T140813/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD  : python3 - <<'\''PY'\''
print(1/0)
PY'
+ echo '- LOG  : reports_auto/panic_20250920T140813/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T140813/run.err'
+ echo '- PY   : reports_auto/panic_20250920T140813/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T140813/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T140813/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T140813/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250920T140813/run.err reports_auto/panic_20250920T140813/python_stderr.txt
+ grep -qi 'No module named '\''tools'\''' reports_auto/panic_20250920T140813/run.err reports_auto/panic_20250920T140813/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250920T140813/run.err reports_auto/panic_20250920T140813/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250920T140813/run.err reports_auto/panic_20250920T140813/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T140813/oom.txt
+ grep -qi 'No such file or directory' reports_auto/panic_20250920T140813/run.err reports_auto/panic_20250920T140813/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250920T140813/run.err reports_auto/panic_20250920T140813/python_stderr.txt
+ set +x
