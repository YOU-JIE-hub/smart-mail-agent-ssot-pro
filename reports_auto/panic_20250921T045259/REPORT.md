# Panic Report
- Exit code: 3
- CMD  : python3 - <<PY
import sys, time
print("panic smoke ok")
time.sleep(0.1)
sys.exit(3)
PY
- LOG  : reports_auto/panic_20250921T045259/run.log
- ERR  : reports_auto/panic_20250921T045259/run.err
- PY   : reports_auto/panic_20250921T045259/python_stderr.txt
- OOM  : reports_auto/panic_20250921T045259/oom.txt
- TRACE: reports_auto/panic_20250921T045259/xtrace.sh
- SYS  : reports_auto/panic_20250921T045259/system.txt

## Heuristics
