SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -Eeuo pipefail -c
.DEFAULT_GOAL := help

HOST ?= 127.0.0.1
PORT ?= 18080
APP  ?= sma.api.service_compat:app

help:
	@echo "Targets:"
	@echo "  probe     - start/hit/stop API; always dump evidence to reports_auto/online/<TS>"
	@echo "  last      - print latest evidence dir"
	@echo "Usage: make probe  or  HOST=127.0.0.1 PORT=18080 make probe"

probe:
	HOST=$(HOST) PORT=$(PORT) APP=$(APP) bash scripts/online_probe.sh

last:
	@echo -n "latest: "; readlink -f reports_auto/online/$$(ls -1t reports_auto/online 2>/dev/null | head -n1) 2>/dev/null || echo NA

## === Online probe & API helpers ===
API_HOST ?= 127.0.0.1
API_PORT ?= 18080
API_APP  ?= sma.api.service_compat:app

.PHONY: probe api-up api-down
probe:
	HOST=$(API_HOST) PORT=$(API_PORT) APP=$(API_APP) bash scripts/online_probe.sh

api-up:
	[ -f .venv/bin/activate ] && . .venv/bin/activate || true; \
	export PYTHONNOUSERSITE=1 PYTHONPATH="src:$$PYTHONPATH"; \
	mkdir -p reports_auto/online && \
	uvicorn $(API_APP) --host $(API_HOST) --port $(API_PORT) --log-level warning

api-down:
	- pkill -f "uvicorn .*:$(API_PORT)" 2>/dev/null || true; ( command -v fuser >/dev/null && fuser -k $(API_PORT)/tcp ) || true
