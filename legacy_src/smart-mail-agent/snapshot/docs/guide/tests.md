# 測試規範與環境
- 測試放於 `tests/`，以 `unit/`, `e2e/`, `contracts/`, `spam/`, `portfolio/` 分類
- 線上相依請加 `@pytest.mark.online`（CI 預設不跑）
- 以 `tests/conftest.py` 自動讀取 `.env.example` 與 `.env`
