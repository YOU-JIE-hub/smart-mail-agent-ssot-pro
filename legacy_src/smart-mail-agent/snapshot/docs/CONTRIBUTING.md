# CONTRIBUTING

Dev setup：
python -m venv ~/.venv/sma
source ~/.venv/sma/bin/activate
pip install -e .[llm,ocr,dev]
pip install pre-commit && pre-commit install
Style：ruff --fix、black(100)、isort(profile=black)
Tests：pytest -q --maxfail=1 --disable-warnings（CI 不觸網）
