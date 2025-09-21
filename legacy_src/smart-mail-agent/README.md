
## Quick Start (Local)

```bash
git clone <your-repo>
cd smart-mail-agent
python -m venv .venv && source .venv/bin/activate
pip install -U pip pytest pytest-cov
PYTHONPATH=.:src make test-all   # 離線跑完整測試與覆蓋率門檻
```

## CI

- 推送 PR 後，GitHub Actions 會自動執行 `make ci`（離線模式），覆蓋率門檻≥85% 才會通過。

