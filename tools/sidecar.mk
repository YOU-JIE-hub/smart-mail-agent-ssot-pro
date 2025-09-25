# --- Sidecar Targets (tabs are literal) ---
PY := python

.PHONY: demo db-init logs-db-check llm-summarize rag-build rag-qa policy-check data-audit model-card

demo:
	@$(PY) scripts/demo_cli.py

db-init:
	@$(PY) -c "from scripts.obs.db import init; init(); print('DB INIT OK')"

logs-db-check:
	@sqlite3 db/sma.sqlite '.tables' 2>/dev/null || echo "set DB_URL to Postgres and ensure driver installed"

llm-summarize:
	@$(PY) scripts/llm/batch_summarize.py

rag-build:
	@$(PY) scripts/rag/build_index.py

rag-qa:
	@test -n "$(Q)" || (echo "Usage: make rag-qa Q='你的問題'"; exit 2)
	@$(PY) scripts/rag/query.py "$(Q)"

policy-check:
	@$(PY) scripts/policy/validate.py

data-audit:
	@$(PY) scripts/data/profile_data.py
	@$(PY) scripts/data/clean_data.py

model-card:
	@$(PY) scripts/eval/model_card.py
