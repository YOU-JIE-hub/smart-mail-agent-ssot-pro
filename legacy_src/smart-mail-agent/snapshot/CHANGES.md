
## chore(tools): 新增 tools/dev-check.sh 分組測試腳本
- 提供命令：
  - `list`: 列出 tests* 內引用到的專案模組（去重）
  - `g1..g5`: 對應分組回歸
  - `all`: 全套測試
  - `cov`: 覆蓋率（term-missing）
- 預設 `OFFLINE=1`，避免對外連線；自動清理 `__pycache__`
- 不修改任何功能模組，僅輔助開發與回歸，避免汙染


## test coverage: add targeted tests for ai_rpa main/actions/nlp_llm
- 新增 `tests/coverage/test_ai_rpa_main_more_paths.py`：覆蓋 unknown task 與 actions-only 的 CLI 路徑
- 新增 `tests/coverage/test_actions_unit_smoke.py`：對 actions 決策函式做最小化單元 smoke（dry-run）
- 新增 `tests/coverage/test_nlp_llm_import_smoke.py`：確保 nlp_llm 可導入並具備可呼叫項（離線 smoke）
- 僅新增測試，**不修改任何功能模組**，避免汙染
