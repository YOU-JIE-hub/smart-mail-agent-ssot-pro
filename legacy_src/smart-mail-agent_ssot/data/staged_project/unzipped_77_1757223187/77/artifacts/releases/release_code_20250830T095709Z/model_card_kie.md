# KIE Model Card (frozen 20250830T054845Z)

## Datasets & Rules
- gold: `data/kie/test_real.jsonl` (sha: b473384245b1de4a26b2144840dff70c018f61ffad04966a209a8f187acaa42b)
- silver_train: `data/kie/silver_train.jsonl` (sha: 344f761c13829627027406637de64172efcad616e19122db091a3b6e7c8b5cd3)
- silver_val: `data/kie/silver_val.jsonl` (sha: bbe2df434570b88cbb2ef56ca8847f7de88d22f184bb2203dbb0178abb157c9a)
- ruleset: `.sma_tools/ruleset.yml` (sha: a5346ac5c1ce4e547fdb9d0ca178430743a1d0e4ea15773c6ba5fa3b05807a8a)

## Metrics (strict / per-field)
- SNAP:      aligned_rows=24 strict_span_P=0.9643 strict_span_R=0.6279  | # field metrics @ 2025-08-30T05:48:45.129184Z amount_P=1.0000 amount_R=0.7500 amount_F1=0.8571  (tp=6, fp=0, fn=2) date_time_P=0.9286 date_time_R=0.8667 date_time_F1=0.8966  (tp=13, fp=1, fn=2) env_P=1.0000 env_R=0.6667 env_F1=0.8000  (tp=6, fp=0, fn=3)
- POS+SNAP:  aligned_rows=24 strict_span_P=0.9667 strict_span_R=0.6744  | # field metrics @ 2025-08-30T05:48:45.143230Z amount_P=1.0000 amount_R=0.7500 amount_F1=0.8571  (tp=6, fp=0, fn=2) date_time_P=0.9286 date_time_R=0.8667 date_time_F1=0.8966  (tp=13, fp=1, fn=2) env_P=1.0000 env_R=0.5556 env_F1=0.7143  (tp=5, fp=0, fn=4)
- ENSEMBLE:  aligned_rows=24 strict_span_P=0.8889 strict_span_R=0.7442  | # field metrics @ 2025-08-30T05:48:45.156993Z amount_P=0.6667 amount_R=0.7500 amount_F1=0.7059  (tp=6, fp=3, fn=2) date_time_P=0.9286 date_time_R=0.8667 date_time_F1=0.8966  (tp=13, fp=1, fn=2) env_P=1.0000 env_R=0.8889 env_F1=0.9412  (tp=8, fp=0, fn=1)

## Deployment Plan
- Serving: model → snap-decode → union with regex (回退)
- Rollout: shadow 1w → if stable, switch primary.
