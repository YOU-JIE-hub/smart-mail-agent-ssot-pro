# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
from pathlib import Path
m = Path("Makefile.compat")
m.write_text(
".PHONY: eval-compat summary-md smoke\n\n"
"eval-compat:\n"
"\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --out reports_auto/summary.json\x27\n\n"
"summary-md:\n"
"\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/build_summary_md.py\x27\n\n"
"smoke:\n"
"\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --smoke --print-classes\x27\n",
"utf-8"
)
mk = Path("Makefile")
txt = mk.read_text("utf-8", errors="ignore") if mk.exists() else ""
if "Makefile.compat" not in txt:
    mk.write_text(txt + "\n-include Makefile.compat\n", "utf-8")
print("[OK] Makefile.compat written with TABs & included")
PY
- LOG  : reports_auto/panic_20250921T132225/run.log
- ERR  : reports_auto/panic_20250921T132225/run.err
- PY   : reports_auto/panic_20250921T132225/python_stderr.txt
- OOM  : reports_auto/panic_20250921T132225/oom.txt
- TRACE: reports_auto/panic_20250921T132225/xtrace.sh
- SYS  : reports_auto/panic_20250921T132225/system.txt

## Heuristics
