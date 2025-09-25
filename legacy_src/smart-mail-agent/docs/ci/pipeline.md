# 企業級 CI 檢查項目
- 語法與風格：ruff
- 型別檢查：mypy（寬鬆模式，不阻斷 PR）
- 單元測試：pytest（預設排除 `online` 標記）
- 安全審視：pip-audit（相依套件）、bandit（靜態分析）
- 文件檢查：mkdocs build（僅建置，不部署）
