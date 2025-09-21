+ CMD='PYTHONPATH=. python3 scripts/use_spam_model.py --model "\\wsl.localhost\Ubuntu-22.04\home\youjie\projects\smart-mail-agent_ssot\artifacts_inbox\spam\artifacts_prod\model_pipeline.pkl"'
+ '[' -z 'PYTHONPATH=. python3 scripts/use_spam_model.py --model "\\wsl.localhost\Ubuntu-22.04\home\youjie\projects\smart-mail-agent_ssot\artifacts_inbox\spam\artifacts_prod\model_pipeline.pkl"' ']'
+ echo '== SNAPSHOT 20250920T135822 =='
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
+ timeout --preserve-status 3h bash -lc 'PYTHONPATH=. python3 scripts/use_spam_model.py --model "\\wsl.localhost\Ubuntu-22.04\home\youjie\projects\smart-mail-agent_ssot\artifacts_inbox\spam\artifacts_prod\model_pipeline.pkl"'
++ tee -a reports_auto/panic_20250920T135822/python_stderr.txt
+ ec=2
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 2'
+ echo '- CMD  : PYTHONPATH=. python3 scripts/use_spam_model.py --model "\\wsl.localhost\Ubuntu-22.04\home\youjie\projects\smart-mail-agent_ssot\artifacts_inbox\spam\artifacts_prod\model_pipeline.pkl"'
+ echo '- LOG  : reports_auto/panic_20250920T135822/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T135822/run.err'
+ echo '- PY   : reports_auto/panic_20250920T135822/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T135822/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T135822/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T135822/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250920T135822/run.err reports_auto/panic_20250920T135822/python_stderr.txt
+ grep -qi 'ModuleNotFoundError: No module named '\''tools'\''' reports_auto/panic_20250920T135822/run.err reports_auto/panic_20250920T135822/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250920T135822/run.err reports_auto/panic_20250920T135822/python_stderr.txt
+ grep -qi 'No such file or directory' reports_auto/panic_20250920T135822/run.err reports_auto/panic_20250920T135822/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250920T135822/run.err reports_auto/panic_20250920T135822/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T135822/oom.txt
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ echo reports_auto/panic_20250920T135822/REPORT.md
+ echo reports_auto/panic_20250920T135822/python_stderr.txt
+ echo reports_auto/panic_20250920T135822/run.err
+ echo reports_auto/panic_20250920T135822/run.log
+ echo reports_auto/panic_20250920T135822/xtrace.sh
+ echo reports_auto/panic_20250920T135822/system.txt
+ echo reports_auto/panic_20250920T135822/oom.txt
+ echo
+ exit 2
