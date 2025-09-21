# Panic Report
- Exit code: 1
- CMD: python3 scripts/canuse_scan_and_train.py
- LOG : reports_auto/panic_20250920T081549/run.log
- ERR : reports_auto/panic_20250920T081549/run.err
- PY  : reports_auto/panic_20250920T081549/python_stderr.txt
- OOM : reports_auto/panic_20250920T081549/oom.txt
- TRACE: reports_auto/panic_20250920T081549/xtrace.sh
- SYS : reports_auto/panic_20250920T081549/system.txt

## Heuristics
- 可能 **OOM 被系統殺掉**（stderr 有 Killed）
- dmesg 顯示 **Out of memory**
- 舊 intent .pkl 需要 __main__.rules_feat（反序列化相容性問題）
- 特徵維度不對齊（向量器詞彙不同）
- 路徑不存在
- 權限問題
