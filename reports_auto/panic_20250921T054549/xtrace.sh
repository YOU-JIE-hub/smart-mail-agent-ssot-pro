+ CMD='
python3 - <<PY
import os, joblib
print("[INTENT_PKL]", os.environ.get("INTENT_PKL"))
print("[SPAM_PKL]  ", os.environ.get("SPAM_PKL"))
# intent 多分類
m_int = joblib.load(os.environ["INTENT_PKL"])
print("intent classes:", getattr(getattr(m_int, "classes_", None), "tolist", lambda: m_int.classes_)())
print("intent pred   :", m_int.predict(["想查一下合約報價和付款方式"])[0])

# spam 二分類
m_spam = joblib.load(os.environ["SPAM_PKL"])
print("spam classes  :", getattr(getattr(m_spam, "classes_", None), "tolist", lambda: m_spam.classes_)())
print("spam pred     :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY
'
+ '[' -z '
python3 - <<PY
import os, joblib
print("[INTENT_PKL]", os.environ.get("INTENT_PKL"))
print("[SPAM_PKL]  ", os.environ.get("SPAM_PKL"))
# intent 多分類
m_int = joblib.load(os.environ["INTENT_PKL"])
print("intent classes:", getattr(getattr(m_int, "classes_", None), "tolist", lambda: m_int.classes_)())
print("intent pred   :", m_int.predict(["想查一下合約報價和付款方式"])[0])

# spam 二分類
m_spam = joblib.load(os.environ["SPAM_PKL"])
print("spam classes  :", getattr(getattr(m_spam, "classes_", None), "tolist", lambda: m_spam.classes_)())
print("spam pred     :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY
' ']'
+ echo '== SNAPSHOT 20250921T054549 =='
+ pwd
+ python3 -V
+ pip -V
+ which -a python3
+ free -h
+ df -h .
+ ulimit -a
+ env
+ grep -E 'INTENT_PKL|SPAM_PKL|PYTHONPATH'
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ set +e
+ timeout --preserve-status 3h bash -lc '
python3 - <<PY
import os, joblib
print("[INTENT_PKL]", os.environ.get("INTENT_PKL"))
print("[SPAM_PKL]  ", os.environ.get("SPAM_PKL"))
# intent 多分類
m_int = joblib.load(os.environ["INTENT_PKL"])
print("intent classes:", getattr(getattr(m_int, "classes_", None), "tolist", lambda: m_int.classes_)())
print("intent pred   :", m_int.predict(["想查一下合約報價和付款方式"])[0])

# spam 二分類
m_spam = joblib.load(os.environ["SPAM_PKL"])
print("spam classes  :", getattr(getattr(m_spam, "classes_", None), "tolist", lambda: m_spam.classes_)())
print("spam pred     :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY
'
++ tee -a reports_auto/panic_20250921T054549/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : 
python3 - <<PY
import os, joblib
print("[INTENT_PKL]", os.environ.get("INTENT_PKL"))
print("[SPAM_PKL]  ", os.environ.get("SPAM_PKL"))
# intent 多分類
m_int = joblib.load(os.environ["INTENT_PKL"])
print("intent classes:", getattr(getattr(m_int, "classes_", None), "tolist", lambda: m_int.classes_)())
print("intent pred   :", m_int.predict(["想查一下合約報價和付款方式"])[0])

# spam 二分類
m_spam = joblib.load(os.environ["SPAM_PKL"])
print("spam classes  :", getattr(getattr(m_spam, "classes_", None), "tolist", lambda: m_spam.classes_)())
print("spam pred     :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY
'
+ echo '- LOG  : reports_auto/panic_20250921T054549/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T054549/run.err'
+ echo '- PY   : reports_auto/panic_20250921T054549/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T054549/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T054549/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T054549/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi 'Can'\''t get attribute '\''rules_feat' reports_auto/panic_20250921T054549/run.err reports_auto/panic_20250921T054549/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T054549/run.err reports_auto/panic_20250921T054549/python_stderr.txt
+ grep -qi 'ModuleNotFoundError: No module named' reports_auto/panic_20250921T054549/run.err reports_auto/panic_20250921T054549/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T054549/run.err reports_auto/panic_20250921T054549/python_stderr.txt
+ grep -qi 'out of memory' reports_auto/panic_20250921T054549/oom.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T054549/REPORT.md\nreports_auto/panic_20250921T054549/run.log\nreports_auto/panic_20250921T054549/run.err\nreports_auto/panic_20250921T054549/python_stderr.txt\nreports_auto/panic_20250921T054549/xtrace.sh\nreports_auto/panic_20250921T054549/system.txt\nreports_auto/panic_20250921T054549/oom.txt\n'
+ exit 0
