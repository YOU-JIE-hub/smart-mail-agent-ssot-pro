+ CMD='. .venv/bin/activate; python3 - <<'\''PY'\''
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
PY'
+ '[' -z '. .venv/bin/activate; python3 - <<'\''PY'\''
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
PY' ']'
+ echo '== SNAPSHOT 20250921T132225 =='
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
+ timeout --preserve-status 3h bash -lc '. .venv/bin/activate; python3 - <<'\''PY'\''
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
PY'
++ tee -a reports_auto/panic_20250921T132225/python_stderr.txt
+ ec=0
+ set -e
+ echo '== dmesg tail (OOM related) =='
+ dmesg
+ egrep -i 'killed process|out of memory|oom'
+ tail -n 120
+ true
+ echo '# Panic Report'
+ echo '- Exit code: 0'
+ echo '- CMD  : . .venv/bin/activate; python3 - <<'\''PY'\''
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
PY'
+ echo '- LOG  : reports_auto/panic_20250921T132225/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T132225/run.err'
+ echo '- PY   : reports_auto/panic_20250921T132225/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T132225/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T132225/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T132225/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T132225/run.err reports_auto/panic_20250921T132225/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T132225/run.err reports_auto/panic_20250921T132225/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T132225/run.err reports_auto/panic_20250921T132225/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T132225/run.err reports_auto/panic_20250921T132225/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T132225/REPORT.md\nreports_auto/panic_20250921T132225/run.log\nreports_auto/panic_20250921T132225/run.err\nreports_auto/panic_20250921T132225/python_stderr.txt\nreports_auto/panic_20250921T132225/xtrace.sh\nreports_auto/panic_20250921T132225/system.txt\nreports_auto/panic_20250921T132225/oom.txt\n'
+ exit 0
