.PHONY: venv deps fmt lint test
venv: ; python -m venv .venv_clean
deps: ; . .venv_clean/bin/activate && pip install -U pip wheel setuptools && pip install -r requirements.txt || true
fmt: ; . .venv_clean/bin/activate && python -m black src tests
lint: ; . .venv_clean/bin/activate && python -m ruff check src tests
test: ; . .venv_clean/bin/activate && pytest
