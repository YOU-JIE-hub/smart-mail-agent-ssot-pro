+ CMD='python3 - <<PY
import sys, time
print("panic smoke ok")
time.sleep(0.1)
sys.exit(3)
PY'
+ '[' -z 'python3 - <<PY
import sys, time
print("panic smoke ok")
time.sleep(0.1)
sys.exit(3)
PY' ']'
+ echo '== SNAPSHOT 20250921T042521 =='
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
+ timeout --preserve-status 3h bash -lc 'python3 - <<PY
import sys, time
print("panic smoke ok")
time.sleep(0.1)
sys.exit(3)
PY'
++ tee -a reports_auto/panic_20250921T042521/python_stderr.txt
+ ec=3
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 3'
+ echo '- CMD  : python3 - <<PY
import sys, time
print("panic smoke ok")
time.sleep(0.1)
sys.exit(3)
PY'
+ echo '- LOG  : reports_auto/panic_20250921T042521/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T042521/run.err'
+ echo '- PY   : reports_auto/panic_20250921T042521/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T042521/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T042521/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T042521/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250921T042521/run.err reports_auto/panic_20250921T042521/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250921T042521/run.err reports_auto/panic_20250921T042521/python_stderr.txt
+ grep -qi 'ModuleNotFoundError: No module named '\''tools'\''' reports_auto/panic_20250921T042521/run.err reports_auto/panic_20250921T042521/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T042521/run.err reports_auto/panic_20250921T042521/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250921T042521/oom.txt
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ printf '%s\n' reports_auto/panic_20250921T042521/REPORT.md reports_auto/panic_20250921T042521/run.log reports_auto/panic_20250921T042521/run.err reports_auto/panic_20250921T042521/python_stderr.txt reports_auto/panic_20250921T042521/xtrace.sh reports_auto/panic_20250921T042521/system.txt reports_auto/panic_20250921T042521/oom.txt
+ echo
+ exit 3
