# Panic Report
- Exit code: 1
- CMD  : . .venv/bin/activate; python3 - <<'PY' 
from pathlib import Path
frag = (
".PHONY: eval-compat summary-md smoke\\n\\n"
"eval-compat:\\n"
"\\t@bash tools/panic.sh \\ . .venv/bin/activate
- LOG  : reports_auto/panic_20250921T124413/run.log
- ERR  : reports_auto/panic_20250921T124413/run.err
- PY   : reports_auto/panic_20250921T124413/python_stderr.txt
- OOM  : reports_auto/panic_20250921T124413/oom.txt
- TRACE: reports_auto/panic_20250921T124413/xtrace.sh
- SYS  : reports_auto/panic_20250921T124413/system.txt

## Heuristics
