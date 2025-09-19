PY=python3
LOGDIR=reports_auto/logs
DATE:=$(shell date +%F)

.PHONY: train_all train_intent train_spam eval_kie smoke serve verify

train_all: train_intent train_spam eval_kie verify

train_intent:
	@mkdir -p $(LOGDIR)
	@PYTHONNOUSERSITE=1 PYTHONPATH=$(PWD):$(PWD)/src:$(PWD)/vendor:$$PYTHONPATH \
	$(PY) src/trainers/train_intent.py 1>$(LOGDIR)/train_intent.$(DATE).log 2>$(LOGDIR)/train_intent.$(DATE).err || ( explorer.exe "$$(wslpath -w $(LOGDIR))" >/dev/null 2>&1 || true; false )

train_spam:
	@mkdir -p $(LOGDIR)
	@PYTHONNOUSERSITE=1 PYTHONPATH=$(PWD):$(PWD)/src:$(PWD)/vendor:$$PYTHONPATH \
	$(PY) src/trainers/train_spam.py 1>$(LOGDIR)/train_spam.$(DATE).log 2>$(LOGDIR)/train_spam.$(DATE).err || ( explorer.exe "$$(wslpath -w $(LOGDIR))" >/dev/null 2>&1 || true; false )

eval_kie:
	@mkdir -p $(LOGDIR)
	@PYTHONNOUSERSITE=1 PYTHONPATH=$(PWD):$(PWD)/src:$(PWD)/vendor:$$PYTHONPATH \
	$(PY) src/trainers/eval_kie_regex.py 1>$(LOGDIR)/eval_kie.$(DATE).log 2>$(LOGDIR)/eval_kie.$(DATE).err || ( explorer.exe "$$(wslpath -w $(LOGDIR))" >/dev/null 2>&1 || true; false )

smoke:
	@mkdir -p data/intent_eval data/spam_eval data/kie_eval
	@[ -s data/intent_eval/dataset.cleaned.jsonl ] || printf '%s\n' '{"id":"ex1","text":"請幫我報價 10 台伺服器","label":"biz_quote"}' '{"id":"ex2","text":"我要退貨，請協助處理","label":"return"}' > data/intent_eval/dataset.cleaned.jsonl
	@[ -s data/spam_eval/dataset.jsonl ] || printf '%s\n' '{"id":"s1","text":"【免費中獎】點我領取 1000 美金！","label":1}' '{"id":"s2","text":"會議紀要已附上，請查收。","label":0}' > data/spam_eval/dataset.jsonl
	@[ -s data/kie_eval/gold_merged.jsonl ] || printf '%s\n' '{"id":"k1","text":"訂單 SO-2025-0918 共 5 件，總額 TWD 12,500；聯絡 02-1234-5678","labels":{"order_id":"SO-2025-0918","amount":"12500","phone":"02-1234-5678"}}' > data/kie_eval/gold_merged.jsonl
	@echo "[smoke] minimal datasets are in place."

serve:
	@fuser -k -n tcp 8088 >/dev/null 2>&1 || true
	@nohup $(PY) -m uvicorn scripts.api_meta:app --host 127.0.0.1 --port 8088 >> reports_auto/api/api.out 2>> reports_auto/api/api.err & echo $$! > reports_auto/api/api.pid && \
	echo "API: http://127.0.0.1:8088/debug/model_meta (pid $$(cat reports_auto/api/api.pid))"

verify:
	@echo "== INTENT =="; cat models/intent/registry.json 2>/dev/null || echo "no registry"
	@echo "== SPAM   =="; cat models/spam/registry.json 2>/dev/null || echo "no registry"
	@echo "== KIE    =="; cat models/kie/registry.json 2>/dev/null || echo "no registry"
