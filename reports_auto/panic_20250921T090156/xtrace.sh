+ CMD='python3 - <<PY
import os, joblib
m_int=joblib.load(os.environ["INTENT_PKL"])
m_spam=joblib.load(os.environ["SPAM_PKL"])
print("intent classes:", getattr(m_int,"classes_",[]))
print("intent pred   :", m_int.predict(["想查一下合約報價與付款方式"])[0])
print("spam classes  :", getattr(m_spam,"classes_",[]))
print("spam pred     :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY'
+ '[' -z 'python3 - <<PY
import os, joblib
m_int=joblib.load(os.environ["INTENT_PKL"])
m_spam=joblib.load(os.environ["SPAM_PKL"])
print("intent classes:", getattr(m_int,"classes_",[]))
print("intent pred   :", m_int.predict(["想查一下合約報價與付款方式"])[0])
print("spam classes  :", getattr(m_spam,"classes_",[]))
print("spam pred     :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY' ']'
+ echo '== SNAPSHOT 20250921T090156 =='
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
+ timeout --preserve-status 3h bash -lc 'python3 - <<PY
import os, joblib
m_int=joblib.load(os.environ["INTENT_PKL"])
m_spam=joblib.load(os.environ["SPAM_PKL"])
print("intent classes:", getattr(m_int,"classes_",[]))
print("intent pred   :", m_int.predict(["想查一下合約報價與付款方式"])[0])
print("spam classes  :", getattr(m_spam,"classes_",[]))
print("spam pred     :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY'
++ tee -a reports_auto/panic_20250921T090156/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : python3 - <<PY
import os, joblib
m_int=joblib.load(os.environ["INTENT_PKL"])
m_spam=joblib.load(os.environ["SPAM_PKL"])
print("intent classes:", getattr(m_int,"classes_",[]))
print("intent pred   :", m_int.predict(["想查一下合約報價與付款方式"])[0])
print("spam classes  :", getattr(m_spam,"classes_",[]))
print("spam pred     :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY'
+ echo '- LOG  : reports_auto/panic_20250921T090156/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T090156/run.err'
+ echo '- PY   : reports_auto/panic_20250921T090156/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T090156/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T090156/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T090156/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T090156/run.err reports_auto/panic_20250921T090156/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T090156/run.err reports_auto/panic_20250921T090156/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T090156/run.err reports_auto/panic_20250921T090156/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T090156/run.err reports_auto/panic_20250921T090156/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T090156/REPORT.md\nreports_auto/panic_20250921T090156/run.log\nreports_auto/panic_20250921T090156/run.err\nreports_auto/panic_20250921T090156/python_stderr.txt\nreports_auto/panic_20250921T090156/xtrace.sh\nreports_auto/panic_20250921T090156/system.txt\nreports_auto/panic_20250921T090156/oom.txt\n'
+ exit 0
