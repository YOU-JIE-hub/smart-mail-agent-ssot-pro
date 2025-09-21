# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<PY
import os, joblib
import tools.compat_loader # noqa: F401
m_int=joblib.load(os.environ["INTENT_PKL"])
m_spam=joblib.load(os.environ["SPAM_PKL"])
print("intent classes:", getattr(m_int,"classes_",[]))
print("intent pred :", m_int.predict(["想查一下合約報價與付款方式"])[0])
print("spam classes :", getattr(m_spam,"classes_",[]))
print("spam pred :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY
- LOG  : reports_auto/panic_20250921T121245/run.log
- ERR  : reports_auto/panic_20250921T121245/run.err
- PY   : reports_auto/panic_20250921T121245/python_stderr.txt
- OOM  : reports_auto/panic_20250921T121245/oom.txt
- TRACE: reports_auto/panic_20250921T121245/xtrace.sh
- SYS  : reports_auto/panic_20250921T121245/system.txt

## Heuristics
