+ CMD='rsync -a --prune-empty-dirs --delete --max-size=10m --filter='\''merge /tmp/code_filter.rsync'\'' "/home/youjie/projects/smart-mail-agent"/ "/home/youjie/projects/smart-mail-agent-ssot-pro/legacy_src/smart-mail-agent"/'
+ '[' -z 'rsync -a --prune-empty-dirs --delete --max-size=10m --filter='\''merge /tmp/code_filter.rsync'\'' "/home/youjie/projects/smart-mail-agent"/ "/home/youjie/projects/smart-mail-agent-ssot-pro/legacy_src/smart-mail-agent"/' ']'
+ echo '== SNAPSHOT 20250921T135122 =='
+ pwd
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT|SPAM|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc 'rsync -a --prune-empty-dirs --delete --max-size=10m --filter='\''merge /tmp/code_filter.rsync'\'' "/home/youjie/projects/smart-mail-agent"/ "/home/youjie/projects/smart-mail-agent-ssot-pro/legacy_src/smart-mail-agent"/'
++ tee -a reports_auto/panic_20250921T135122/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : rsync -a --prune-empty-dirs --delete --max-size=10m --filter='\''merge /tmp/code_filter.rsync'\'' "/home/youjie/projects/smart-mail-agent"/ "/home/youjie/projects/smart-mail-agent-ssot-pro/legacy_src/smart-mail-agent"/'
+ echo '- LOG  : reports_auto/panic_20250921T135122/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T135122/run.err'
+ echo '- PY   : reports_auto/panic_20250921T135122/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T135122/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T135122/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T135122/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T135122/run.err reports_auto/panic_20250921T135122/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T135122/run.err reports_auto/panic_20250921T135122/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T135122/run.err reports_auto/panic_20250921T135122/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T135122/run.err reports_auto/panic_20250921T135122/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T135122/REPORT.md\nreports_auto/panic_20250921T135122/run.log\nreports_auto/panic_20250921T135122/run.err\nreports_auto/panic_20250921T135122/python_stderr.txt\nreports_auto/panic_20250921T135122/xtrace.sh\nreports_auto/panic_20250921T135122/system.txt\nreports_auto/panic_20250921T135122/oom.txt\n'
+ exit 0
