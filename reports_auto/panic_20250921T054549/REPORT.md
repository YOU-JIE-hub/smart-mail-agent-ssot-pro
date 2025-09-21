# Panic Report
- Exit code: 0
- CMD  : 
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

- LOG  : reports_auto/panic_20250921T054549/run.log
- ERR  : reports_auto/panic_20250921T054549/run.err
- PY   : reports_auto/panic_20250921T054549/python_stderr.txt
- OOM  : reports_auto/panic_20250921T054549/oom.txt
- TRACE: reports_auto/panic_20250921T054549/xtrace.sh
- SYS  : reports_auto/panic_20250921T054549/system.txt

## Heuristics
