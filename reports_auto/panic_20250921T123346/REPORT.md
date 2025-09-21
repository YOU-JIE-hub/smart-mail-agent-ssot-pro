# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
import os, joblib, json, pathlib
from sklearn.metrics import classification_report, accuracy_score
root=pathlib.Path(".")
X_int=[json.loads(x)["text"] for x in (root/"data/intent_eval/test.jsonl").read_text("utf-8").splitlines()]
y_int=[json.loads(x)["label"] for x in (root/"data/intent_eval/test.jsonl").read_text("utf-8").splitlines()]
m_int=joblib.load(os.environ["INTENT_PKL"])
m_spam=joblib.load(os.environ["SPAM_PKL"])
print("intent classes:", getattr(m_int,"classes_",[]))
print("intent pred   :", m_int.predict(["想查一下合約報價與付款方式"])[0])
print("spam classes  :", getattr(m_spam,"classes_",[]))
print("spam pred     :", m_spam.predict(["FREE $$$ click here!!!"])[0])
PY
- LOG  : reports_auto/panic_20250921T123346/run.log
- ERR  : reports_auto/panic_20250921T123346/run.err
- PY   : reports_auto/panic_20250921T123346/python_stderr.txt
- OOM  : reports_auto/panic_20250921T123346/oom.txt
- TRACE: reports_auto/panic_20250921T123346/xtrace.sh
- SYS  : reports_auto/panic_20250921T123346/system.txt

## Heuristics
