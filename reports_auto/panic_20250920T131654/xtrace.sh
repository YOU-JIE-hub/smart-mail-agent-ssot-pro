+ CMD='PYTHONPATH=. python3 scripts/find_training_data.py --roots /home/youjie/projects/smart-mail-agent /home/youjie/projects/smart-mail-agent_ssot /home/youjie/projects/smart-mail-agent-ssot-pro --model-intent ${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl} --model-spam ${SPAM_PKL:-models/spam/artifacts/model_pipeline.pkl}'
+ '[' -z 'PYTHONPATH=. python3 scripts/find_training_data.py --roots /home/youjie/projects/smart-mail-agent /home/youjie/projects/smart-mail-agent_ssot /home/youjie/projects/smart-mail-agent-ssot-pro --model-intent ${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl} --model-spam ${SPAM_PKL:-models/spam/artifacts/model_pipeline.pkl}' ']'
+ echo '== SNAPSHOT 20250920T131654 =='
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
+ timeout --preserve-status 3h bash -lc 'PYTHONPATH=. python3 scripts/find_training_data.py --roots /home/youjie/projects/smart-mail-agent /home/youjie/projects/smart-mail-agent_ssot /home/youjie/projects/smart-mail-agent-ssot-pro --model-intent ${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl} --model-spam ${SPAM_PKL:-models/spam/artifacts/model_pipeline.pkl}'
++ tee -a reports_auto/panic_20250920T131654/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : PYTHONPATH=. python3 scripts/find_training_data.py --roots /home/youjie/projects/smart-mail-agent /home/youjie/projects/smart-mail-agent_ssot /home/youjie/projects/smart-mail-agent-ssot-pro --model-intent ${INTENT_PKL:-models/intent/artifacts/model_pipeline.pkl} --model-spam ${SPAM_PKL:-models/spam/artifacts/model_pipeline.pkl}'
+ echo '- LOG  : reports_auto/panic_20250920T131654/run.log'
+ echo '- ERR  : reports_auto/panic_20250920T131654/run.err'
+ echo '- PY   : reports_auto/panic_20250920T131654/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250920T131654/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250920T131654/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250920T131654/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'only one class' reports_auto/panic_20250920T131654/run.err reports_auto/panic_20250920T131654/python_stderr.txt
+ grep -qi 'ModuleNotFoundError: No module named '\''tools'\''' reports_auto/panic_20250920T131654/run.err reports_auto/panic_20250920T131654/python_stderr.txt
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250920T131654/run.err reports_auto/panic_20250920T131654/python_stderr.txt
+ grep -qi 'No such file or directory' reports_auto/panic_20250920T131654/run.err reports_auto/panic_20250920T131654/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250920T131654/run.err reports_auto/panic_20250920T131654/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250920T131654/oom.txt
+ echo
+ echo '=== DIAG OUTPUTS ==='
+ echo reports_auto/panic_20250920T131654/REPORT.md
+ echo reports_auto/panic_20250920T131654/python_stderr.txt
+ echo reports_auto/panic_20250920T131654/run.err
+ echo reports_auto/panic_20250920T131654/run.log
+ echo reports_auto/panic_20250920T131654/xtrace.sh
+ echo reports_auto/panic_20250920T131654/system.txt
+ echo reports_auto/panic_20250920T131654/oom.txt
+ echo
+ exit 0
