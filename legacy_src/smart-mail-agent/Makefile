.PHONY: spam-eval intent-eval kie-eval

spam-eval:
	@bash -lc 'source .sma_tools/env_guard.sh; \
	  python scripts/sma_quick_eval.py \
	    --data $(DATA) \
	    --model artifacts_prod/model_pipeline.pkl \
	    --thresholds artifacts_prod/ens_thresholds.json \
	    --out reports_auto/prod_quick_report.md'

intent-eval:
	@bash -lc 'source .sma_tools/env_guard.sh; \
	  python .sma_tools/runtime_threshold_router.py \
	    --model artifacts/intent_pro_cal.pkl \
	    --input data/intent/external_realistic_test.clean.jsonl \
	    --config reports_auto/intent_thresholds.json \
	    --eval'

kie-eval:
	@bash -lc 'source .sma_tools/env_guard.sh; \
	  bash RUNME_kie.sh data/kie/test.jsonl data/kie/test.jsonl'
