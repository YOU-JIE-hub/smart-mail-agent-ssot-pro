#!/usr/bin/env bash
set -Eeuo pipefail
. .venv/bin/activate
python src/ai_rpa/main.py --config configs/ai_rpa_config.yaml --tasks ocr,scrape,classify_files,nlp,actions --output "data/output/$(date +%Y%m%d).json"
