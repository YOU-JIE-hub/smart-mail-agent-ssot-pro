# ===== Makefile (sidecar, zero-intrusion) =====
SHELL := /usr/bin/env bash
VENV_ACT := [ -f .venv/bin/activate ] && . .venv/bin/activate || true
PY_ENV   := export PYTHONNOUSERSITE=1; export PYTHONPATH="$(PWD):$(PWD)/src:$$PYTHONPATH"
PY       := $(VENV_ACT); $(PY_ENV); python
BASH     := $(VENV_ACT); $(PY_ENV); bash
APP ?= sma.api.app:app
export APP
.PHONY: help probe online summary doctor pro-eval pro-md pro-all contracts-validate bundle clean-latest print-env
help:
	@echo ""; \
	echo "Targets:"; \
	echo "  online            - TestClient 探測 6 端點，產 reports_auto/online/<TS>/ 證據"; \
	echo "  summary           - 顯示 online 的 latest 與檔案清單"; \
	echo "  doctor            - 產出環境體檢 reports_auto/status/ENV_DOCTOR_<TS>.{json,md}"; \
	echo "  pro-eval          - 旁路評測：reports_auto/pro/<TS>/summary.json + TSV"; \
	echo "  pro-md            - 依 latest 生成 Markdown 報表 summary.md"; \
	echo "  pro-all           - = pro-eval + pro-md"; \
	echo "  probe             - (=online) 舊名相容"; \
	echo "  contracts-validate- 如有 scripts/contracts/validate.sh 則執行，否則略過"; \
	echo "  bundle            - 合併 pro/latest + online/latest -> bundle_<TS>.zip（若 tools/make_bundle.sh 存在）"; \
	echo "  clean-latest      - 移除 latest 符號連結（不刪產物）"; \
	echo "  print-env         - 顯示關鍵環境與路徑"; \
	echo ""
online:
	@$(BASH) scripts/online_probe_env.sh
probe: online
summary:
	@bash scripts/print_latest_v3.sh
doctor:
	@$(BASH) scripts/obs/env_doctor.sh
pro-eval:
	@set -euo pipefail; \
	if [ -f scripts/eval/pro_eval.py ]; then $(PY) scripts/eval/pro_eval.py; \
	elif [ -f scripts/eval_pro.py ]; then $(PY) scripts/eval_pro.py; \
	elif [ -f eval_pro.py ]; then $(PY) eval_pro.py; \
	else echo "[FATAL] 找不到 pro_eval 腳本" >&2; exit 1; fi
pro-md:
	@set -euo pipefail; \
	if [ -f scripts/eval/build_md.py ]; then $(PY) scripts/eval/build_md.py; \
	elif [ -f scripts/build_pro_md.py ]; then $(PY) scripts/build_pro_md.py; \
	elif [ -f build_pro_md.py ]; then $(PY) build_pro_md.py; \
	else echo "[WARN] 找不到 build_md 腳本，略過 Markdown"; fi
pro-all: pro-eval pro-md
	@echo "OK pro-all -> reports_auto/pro/latest/"
contracts-validate:
	@set -euo pipefail; \
	if [ -x scripts/contracts/validate.sh ]; then $(BASH) scripts/contracts/validate.sh; \
	else echo "[INFO] 無 contracts 驗證腳本，略過。"; fi
bundle:
	@set -euo pipefail; \
	if [ -x tools/make_bundle.sh ]; then bash tools/make_bundle.sh; \
	else echo "[INFO] 無 tools/make_bundle.sh，略過 bundle。"; fi
clean-latest:
	@rm -f reports_auto/online/latest reports_auto/pro/latest || true; echo "[OK] latest symlinks removed."
print-env:
	@echo "APP=$(APP)"; \
	echo "PYTHONPATH=$$PYTHONPATH"; \
	echo "INTENT_PKL=$$INTENT_PKL"; \
	echo "SPAM_PKL=$$SPAM_PKL"; \
	echo "KIE_DIR=$$KIE_DIR"; \
	echo "INTENT_CLASSES_JSON=$$INTENT_CLASSES_JSON"
