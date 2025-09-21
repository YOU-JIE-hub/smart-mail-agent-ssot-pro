# Panic Report
- Exit code: 1
- CMD  : python3 - <<PY
import sys, time
print(\"hello from test\")
time.sleep(0.2)
sys.exit(3)
PY
- LOG  : reports_auto/panic_20250920T123135/run.log
- ERR  : reports_auto/panic_20250920T123135/run.err
- PY   : reports_auto/panic_20250920T123135/python_stderr.txt
- OOM  : reports_auto/panic_20250920T123135/oom.txt
- TRACE: reports_auto/panic_20250920T123135/xtrace.sh
- SYS  : reports_auto/panic_20250920T123135/system.txt

## Heuristics
