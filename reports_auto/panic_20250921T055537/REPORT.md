# Panic Report
- Exit code: 0
- CMD  : 
python3 - <<PY
import os, joblib
m_int  = joblib.load(os.environ["INTENT_PKL"])
m_spam = joblib.load(os.environ["SPAM_PKL"])
print("intent classes:", getattr(getattr(m_int, "classes_", None), "tolist", lambda: m_int.classes_)())
print("intent sample :", m_int.predict(["想查一下合約報價和付款方式"])[0])
print("spam classes  :", getattr(getattr(m_spam,"classes_",None),"tolist",lambda: m_spam.classes_)())
print("spam sample   :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY

- LOG  : reports_auto/panic_20250921T055537/run.log
- ERR  : reports_auto/panic_20250921T055537/run.err
- PY   : reports_auto/panic_20250921T055537/python_stderr.txt
- OOM  : reports_auto/panic_20250921T055537/oom.txt
- TRACE: reports_auto/panic_20250921T055537/xtrace.sh
- SYS  : reports_auto/panic_20250921T055537/system.txt

## Heuristics
