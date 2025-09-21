+ export PYTHONFAULTHANDLER=1
+ PYTHONFAULTHANDLER=1
+ export PYTHONWARNINGS=default
+ PYTHONWARNINGS=default
+ export PYTHONUNBUFFERED=1
+ PYTHONUNBUFFERED=1
+ export PYTHONHASHSEED=0
+ PYTHONHASHSEED=0
+ CMD='python3 scripts/eval_intent.py'
+ '[' -z 'python3 scripts/eval_intent.py' ']'
+ echo '== SNAPSHOT 20250920T114801 =='
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
+ ec=0
+ set +e
+ timeout --preserve-status 3h bash -lc 'python3 scripts/eval_intent.py'
++ tee -a reports_auto/panic_20250920T114801/python_stderr.txt
+ ec=1
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ finish 1
+ local ec=1
+ echo '# Panic Report'
+ echo '- Exit code: 1'
+ echo '- CMD  : python3 scripts/eval_intent.py'
+ echo '- LOG  : reports_auto/panic_20250920T114801/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T114801/run.err'
+ echo '- PY   : reports_auto/panic_20250920T114801/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T114801/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T114801/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T114801/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi Killed reports_auto/panic_20250920T114801/run.err reports_auto/panic_20250920T114801/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T114801/oom.txt
+ grep -qi rules_feat reports_auto/panic_20250920T114801/run.err reports_auto/panic_20250920T114801/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250920T114801/run.err reports_auto/panic_20250920T114801/python_stderr.txt
+ grep -qi 'ModuleNotFoundError: No module named '\''tools'\''' reports_auto/panic_20250920T114801/run.err reports_auto/panic_20250920T114801/python_stderr.txt
+ echo '- PYTHONPATH/工作目錄錯誤，或缺少 tools/__init__.py（已自動補）'
+ grep -qi 'No such file or directory' reports_auto/panic_20250920T114801/run.err reports_auto/panic_20250920T114801/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250920T114801/run.err reports_auto/panic_20250920T114801/python_stderr.txt
+ set +x
