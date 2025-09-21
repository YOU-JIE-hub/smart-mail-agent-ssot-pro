PY=python
PIP=pip

.PHONY: setup fmt lint test smoke run-nlp run-ocr

setup:
	$(PIP) install -e ".[ocr,llm,dev]"

fmt:
	ruff check --fix .
	black .
	isort .

lint:
	ruff check .
	black --check .
	isort --check-only .

test:
	pytest -q

smoke:
	pytest -q tests_smoke

run-nlp:
	ai-rpa --input-path samples/nlp_demo.txt --tasks nlp,actions --output data/output/report.json

run-ocr:
	ai-rpa --input-path samples/ocr_tra.png --tasks ocr,nlp,actions --output data/output/ocr_report.json
