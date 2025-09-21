# Panic Report
- Exit code: 127
- CMD: bash tools/oneclick_realign.sh
- LOG : reports_auto/panic_20250920T081711/run.log
- ERR : reports_auto/panic_20250920T081711/run.err
- PY  : reports_auto/panic_20250920T081711/python_stderr.txt
- OOM : reports_auto/panic_20250920T081711/oom.txt
- TRACE: reports_auto/panic_20250920T081711/xtrace.sh
- SYS : reports_auto/panic_20250920T081711/system.txt

## Heuristics
- 可能 **OOM 被系統殺掉**（stderr 有 Killed）
- dmesg 顯示 **Out of memory**
- 舊 intent .pkl 需要 __main__.rules_feat（反序列化相容性問題）
- 特徵維度不對齊（向量器詞彙不同）
- 路徑不存在
- 權限問題
