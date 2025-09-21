# Panic Report
- Exit code: 0
- CMD  : . .venv/bin/activate; python3 - <<'PY'
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
PY
- LOG  : reports_auto/panic_20250921T132826/run.log
- ERR  : reports_auto/panic_20250921T132826/run.err
- PY   : reports_auto/panic_20250921T132826/python_stderr.txt
- OOM  : reports_auto/panic_20250921T132826/oom.txt
- TRACE: reports_auto/panic_20250921T132826/xtrace.sh
- SYS  : reports_auto/panic_20250921T132826/system.txt

## Heuristics
