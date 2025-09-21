+ CMD='. .venv/bin/activate; python3 scripts/eval_spam.py --cfg configs/model_paths.yaml --data data/spam_eval/test.jsonl'
+ '[' -z '. .venv/bin/activate; python3 scripts/eval_spam.py --cfg configs/model_paths.yaml --data data/spam_eval/test.jsonl' ']'
+ echo '== SNAPSHOT 20250921T115249 =='
+ pwd
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT|SPAM|PYTHONPATH'
+ egrep -i 'killed process|out of memory|oom'
+ dmesg
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc '. .venv/bin/activate; python3 scripts/eval_spam.py --cfg configs/model_paths.yaml --data data/spam_eval/test.jsonl'
++ tee -a reports_auto/panic_20250921T115249/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : . .venv/bin/activate; python3 scripts/eval_spam.py --cfg configs/model_paths.yaml --data data/spam_eval/test.jsonl'
+ echo '- LOG  : reports_auto/panic_20250921T115249/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T115249/run.err'
+ echo '- PY   : reports_auto/panic_20250921T115249/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T115249/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T115249/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T115249/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T115249/run.err reports_auto/panic_20250921T115249/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T115249/run.err reports_auto/panic_20250921T115249/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T115249/run.err reports_auto/panic_20250921T115249/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T115249/run.err reports_auto/panic_20250921T115249/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T115249/REPORT.md\nreports_auto/panic_20250921T115249/run.log\nreports_auto/panic_20250921T115249/run.err\nreports_auto/panic_20250921T115249/python_stderr.txt\nreports_auto/panic_20250921T115249/xtrace.sh\nreports_auto/panic_20250921T115249/system.txt\nreports_auto/panic_20250921T115249/oom.txt\n'
+ exit 0
