# Panic Report
- Exit code: 1
- CMD  : . .venv/bin/activate; python3 scripts/eval_all.py --cfg configs/model_paths.yaml && echo "--- summary ---" && sed -n "1,200p" reports_auto/summary.json
- LOG  : reports_auto/panic_20250921T114754/run.log
- ERR  : reports_auto/panic_20250921T114754/run.err
- PY   : reports_auto/panic_20250921T114754/python_stderr.txt
- OOM  : reports_auto/panic_20250921T114754/oom.txt
- TRACE: reports_auto/panic_20250921T114754/xtrace.sh
- SYS  : reports_auto/panic_20250921T114754/system.txt

## Heuristics
