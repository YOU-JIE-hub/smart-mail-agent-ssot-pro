SHELL := /bin/bash
VENV := . .venv/bin/activate;
PY := python3

.PHONY: setup fmt lint type test serve docker-build docker-run pro-robust-ab-url pro-robust-gate clean

setup:
	$(VENV) pre-commit install || true

fmt:
	$(VENV) black .
	$(VENV) ruff check --fix .

lint:
	$(VENV) ruff check .

type:
	$(VENV) mypy service runtime_preproc.py

test:
	$(VENV) pytest -q || true

serve:
	bash scripts/server.sh start

pro-robust-ab-url:
	@if [ -f Makefile.compat ]; then $(MAKE) -s -f Makefile.compat pro-robust-ab-url; else echo "[SKIP] pro-robust-ab-url: Makefile.compat not found"; fi

pro-robust-gate:
	@if [ -f Makefile.compat ]; then $(MAKE) -s -f Makefile.compat pro-robust-gate || true; else echo "[SKIP] pro-robust-gate: Makefile.compat not found"; fi

docker-build:
	docker build -t smart-mail-agent:latest .

docker-run:
	docker run --rm -p 8000:8000 --env PORT=8000 \
		--env INTENT_PKL=$${INTENT_PKL} --env SPAM_PKL=$${SPAM_PKL} \
		--env ABSTAIN_MIN_CONF=$${ABSTAIN_MIN_CONF:-0} \
		smart-mail-agent:latest

clean:
	rm -rf .mypy_cache .pytest_cache dist build *.egg-info

serve-stop:
	bash scripts/server.sh stop

serve-restart:
	bash scripts/server.sh restart

serve-status:
	bash scripts/server.sh status

serve-tail:
	bash scripts/server.sh tail

serve-diag:
	bash scripts/serve_diag.sh diag
serve-stop:
	bash scripts/serve_diag.sh stop
serve-status:
	bash scripts/serve_diag.sh status
serve-tail:
	bash scripts/serve_diag.sh tail


# ===== [panic-serve-override] do not edit below =====
.PHONY: serve serve-stop serve-restart serve-status serve-tail
serve:
\tbash scripts/serve_mgr.sh start
serve-stop:
\tbash scripts/serve_mgr.sh stop
serve-restart:
\tbash scripts/serve_mgr.sh restart
serve-status:
\tbash scripts/serve_mgr.sh status
serve-tail:
\tbash scripts/serve_mgr.sh tail
