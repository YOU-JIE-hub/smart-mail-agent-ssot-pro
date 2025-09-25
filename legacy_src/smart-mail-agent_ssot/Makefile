SHELL := /usr/bin/bash
.ONESHELL:
BACKEND ?= rule

.PHONY: guard health ci-smoke eval-all e2e-all api-serve api-smoke

guard:
	bash tools/guard_bad_imports.sh

health:
	bash tools/health_check.sh

ci-smoke:
	bash tools/ci_smoke.sh

eval-all:
	BACKEND=$(BACKEND) python tools/tri_model_eval.py

e2e-all:
	BACKEND=$(BACKEND) python tools/e2e_full.py

api-serve:
	python tools/api_server.py

api-smoke:
	python - <<'PY'
import json, urllib.request
def call(path, payload):
    req=urllib.request.Request(f"http://127.0.0.1:8088{path}",
                               data=json.dumps(payload).encode('utf-8'),
                               method="POST",
                               headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=3) as r:
        print(path, "->", r.read().decode())
p={"subject":"[報價] 需要報價","body":"price:200 qty:3"}
for ep in ("/classify","/extract","/plan","/e2e"):
    call(ep,p)
PY
.PHONY: eval-ml e2e-ml ml-spec
eval-ml:
	@python tools/tri_model_eval_ml.py
e2e-ml:
	@python tools/e2e_full_ml.py
ml-spec:
	@python tools/dump_intent_ml_spec.py
