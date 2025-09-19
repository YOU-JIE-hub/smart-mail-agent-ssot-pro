SHELL := /bin/bash
.PHONY: up down smoke eval intent_report gate e2e
up:            ; @bash scripts/api_up_env.sh
down:          ; @bash scripts/api_down.sh || true
smoke:         ; @bash scripts/sanity_all.sh
eval:          ; @bash scripts/tri_eval_fixlabels.sh
intent_report: ; @bash scripts/tri_eval_report.sh
gate:          ; @bash scripts/gate.sh
e2e:           ; @bash scripts/e2e_smoke.sh
