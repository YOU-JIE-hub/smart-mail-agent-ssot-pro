# 貢獻指南
環境：python3 -m venv .venv && . .venv/bin/activate
安裝：pip install -e . && pip install -U pytest pre-commit ruff black isort
分支：feat/*, fix/*, chore/*
提交：<type>: <summary>
品質：pytest -q 與 pre-commit run -a 均需通過
PR：描述動機、變更、測試證據，若影響 .env 請明列
