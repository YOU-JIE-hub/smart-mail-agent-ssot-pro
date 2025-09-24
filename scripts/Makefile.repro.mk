SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -Eeuo pipefail -c
MAKEFLAGS += --no-builtin-rules
.DEFAULT_GOAL := summary

online: probe
probe:
	@bash scripts/online_probe_env.sh

summary:
	@bash scripts/print_latest_v3.sh 2>/dev/null || { echo "scripts/print_latest_v3.sh 不在，先 make probe"; exit 0; }

doctor:
	@OUT="$$(ls -1dt reports_auto/online/*/ 2>/dev/null | head -n1)"; \
	if [ -z "$$OUT" ]; then echo "OUT:<none> 先 make probe"; exit 0; fi; \
	echo "OUT: $$OUT"; \
	echo "—— 端點狀態 ——"; \
	for x in readyz debug_models intent spam kie; do printf "%-14s %s\n" "$$x" "$$(cat "$$OUT/$$x.code" 2>/dev/null || echo NA)"; done; \
	echo "—— 快速診斷 ——"; \
	( command -v jq >/dev/null && jq -r '.intent_pkl // .intent_path // .intent_meta.path // empty' "$$OUT/debug_models.body" ) \
	 || sed -n '1,80p' "$$OUT/debug_models.body" | sed -n 's/.*"intent_\(pkl\|path\)":"\([^"]*\)".*/\2/p'; \
	test -s "$$OUT/uvicorn.err" && tail -n 40 "$$OUT/uvicorn.err" || echo "<no uvicorn.err>"

api-start:
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	HOST="$${HOST:-127.0.0.1}"; PORT="$${PORT:-18080}"; APP="$${APP:-sma.api.service_compat:app}"; \
	OUT="reports_auto/online/manual_$$(date +%Y%m%dT%H%M%S)"; mkdir -p "$$OUT"; \
	echo "[RUN] uvicorn $$APP --host $$HOST --port $$PORT"; \
	uvicorn "$$APP" --host "$$HOST" --port "$$PORT" --log-level warning >"$$OUT/uvicorn.out" 2>"$$OUT/uvicorn.err" & echo -n $$! > "$$OUT/uvicorn.pid"; \
	echo "OUT: $$OUT"

api-stop:
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	PORT="$${PORT:-18080}"; \
	pkill -f "uvicorn .*:$$PORT" 2>/dev/null || true; ( command -v fuser >/dev/null && fuser -k "$${PORT}/tcp" ) || true; \
	echo "stopped :$$PORT"

pro-eval:
	@if [ -f scripts/eval_pro.py ]; then \
		echo "[RUN] eval_pro.py"; python scripts/eval_pro.py || true; \
	else echo "SKIPPED: scripts/eval_pro.py 不存在"; fi

pro-md:
	@if [ -f scripts/build_pro_md.py ]; then \
		echo "[RUN] build_pro_md.py"; python scripts/build_pro_md.py || true; \
	else echo "SKIPPED: scripts/build_pro_md.py 不存在"; fi

pro-all: pro-eval pro-md

bundle:
	@bash tools/make_bundle.sh

retention:
	@bash tools/retention.sh reports_auto/online
