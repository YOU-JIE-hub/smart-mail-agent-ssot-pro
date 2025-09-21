+ CMD='. .venv/bin/activate; python3 - <<'\''PY'\''
import time, pathlib
root=pathlib.Path(".").resolve()
ts=time.strftime("%Y%m%dT%H%M%S")
bak=root/("reports_auto/makefix_"+ts); bak.mkdir(parents=True, exist_ok=True)

mf=root/"Makefile"
if mf.exists():
    (bak/"Makefile.bak").write_text(mf.read_text("utf-8", errors="ignore"), "utf-8")

# 乾淨主 Makefile（不含配方行，無 Tab 需求）
mf.write_text(
    ".PHONY: all eval-compat summary-md smoke\n\n"
    "-include Makefile.compat\n\n"
    "all: eval-compat summary-md\n",
    "utf-8",
)

# 子 Makefile（配方行一律用 \t=Tab）
mfc=root/"Makefile.compat"
mfc.write_text(
    ".PHONY: eval-compat summary-md smoke\n\n"
    "eval-compat:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --out reports_auto/summary.json\x27\n\n"
    "summary-md:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/build_summary_md.py\x27\n\n"
    "smoke:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --smoke --print-classes\x27\n",
    "utf-8",
)

print("[OK] Makefile reset. Backup at:", bak)
PY'
+ '[' -z '. .venv/bin/activate; python3 - <<'\''PY'\''
import time, pathlib
root=pathlib.Path(".").resolve()
ts=time.strftime("%Y%m%dT%H%M%S")
bak=root/("reports_auto/makefix_"+ts); bak.mkdir(parents=True, exist_ok=True)

mf=root/"Makefile"
if mf.exists():
    (bak/"Makefile.bak").write_text(mf.read_text("utf-8", errors="ignore"), "utf-8")

# 乾淨主 Makefile（不含配方行，無 Tab 需求）
mf.write_text(
    ".PHONY: all eval-compat summary-md smoke\n\n"
    "-include Makefile.compat\n\n"
    "all: eval-compat summary-md\n",
    "utf-8",
)

# 子 Makefile（配方行一律用 \t=Tab）
mfc=root/"Makefile.compat"
mfc.write_text(
    ".PHONY: eval-compat summary-md smoke\n\n"
    "eval-compat:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --out reports_auto/summary.json\x27\n\n"
    "summary-md:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/build_summary_md.py\x27\n\n"
    "smoke:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --smoke --print-classes\x27\n",
    "utf-8",
)

print("[OK] Makefile reset. Backup at:", bak)
PY' ']'
+ echo '== SNAPSHOT 20250921T132826 =='
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
import time, pathlib
root=pathlib.Path(".").resolve()
ts=time.strftime("%Y%m%dT%H%M%S")
bak=root/("reports_auto/makefix_"+ts); bak.mkdir(parents=True, exist_ok=True)

mf=root/"Makefile"
if mf.exists():
    (bak/"Makefile.bak").write_text(mf.read_text("utf-8", errors="ignore"), "utf-8")

# 乾淨主 Makefile（不含配方行，無 Tab 需求）
mf.write_text(
    ".PHONY: all eval-compat summary-md smoke\n\n"
    "-include Makefile.compat\n\n"
    "all: eval-compat summary-md\n",
    "utf-8",
)

# 子 Makefile（配方行一律用 \t=Tab）
mfc=root/"Makefile.compat"
mfc.write_text(
    ".PHONY: eval-compat summary-md smoke\n\n"
    "eval-compat:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --out reports_auto/summary.json\x27\n\n"
    "summary-md:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/build_summary_md.py\x27\n\n"
    "smoke:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --smoke --print-classes\x27\n",
    "utf-8",
)

print("[OK] Makefile reset. Backup at:", bak)
PY'
++ tee -a reports_auto/panic_20250921T132826/python_stderr.txt
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
import time, pathlib
root=pathlib.Path(".").resolve()
ts=time.strftime("%Y%m%dT%H%M%S")
bak=root/("reports_auto/makefix_"+ts); bak.mkdir(parents=True, exist_ok=True)

mf=root/"Makefile"
if mf.exists():
    (bak/"Makefile.bak").write_text(mf.read_text("utf-8", errors="ignore"), "utf-8")

# 乾淨主 Makefile（不含配方行，無 Tab 需求）
mf.write_text(
    ".PHONY: all eval-compat summary-md smoke\n\n"
    "-include Makefile.compat\n\n"
    "all: eval-compat summary-md\n",
    "utf-8",
)

# 子 Makefile（配方行一律用 \t=Tab）
mfc=root/"Makefile.compat"
mfc.write_text(
    ".PHONY: eval-compat summary-md smoke\n\n"
    "eval-compat:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --out reports_auto/summary.json\x27\n\n"
    "summary-md:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/build_summary_md.py\x27\n\n"
    "smoke:\n"
    "\t@bash tools/panic.sh \x27. .venv/bin/activate; python3 scripts/eval_all_compat.py --smoke --print-classes\x27\n",
    "utf-8",
)

print("[OK] Makefile reset. Backup at:", bak)
PY'
+ echo '- LOG  : reports_auto/panic_20250921T132826/run.log'
+ echo '- ERR  : reports_auto/panic_20250921T132826/run.err'
+ echo '- PY   : reports_auto/panic_20250921T132826/python_stderr.txt'
+ echo '- OOM  : reports_auto/panic_20250921T132826/oom.txt'
+ echo '- TRACE: reports_auto/panic_20250921T132826/xtrace.sh'
+ echo '- SYS  : reports_auto/panic_20250921T132826/system.txt'
+ echo
+ echo '## Heuristics'
+ grep -qi JSONDecodeError reports_auto/panic_20250921T132826/run.err reports_auto/panic_20250921T132826/python_stderr.txt
+ grep -qi 'Permission denied' reports_auto/panic_20250921T132826/run.err reports_auto/panic_20250921T132826/python_stderr.txt
+ grep -qi Killed reports_auto/panic_20250921T132826/run.err reports_auto/panic_20250921T132826/python_stderr.txt
+ grep -qi 'only one class' reports_auto/panic_20250921T132826/run.err reports_auto/panic_20250921T132826/python_stderr.txt
+ echo -e '\n=== DIAG OUTPUTS ===\nreports_auto/panic_20250921T132826/REPORT.md\nreports_auto/panic_20250921T132826/run.log\nreports_auto/panic_20250921T132826/run.err\nreports_auto/panic_20250921T132826/python_stderr.txt\nreports_auto/panic_20250921T132826/xtrace.sh\nreports_auto/panic_20250921T132826/system.txt\nreports_auto/panic_20250921T132826/oom.txt\n'
+ exit 0
