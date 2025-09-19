SHELL := /bin/bash
PY := python

.PHONY: run.tri run.kie db.migrate db.views db.snapshot bundle.support health

run.tri:
\t$(PY) tools/tri_suite.py || true
\tls -t reports_auto/eval/*/tri_suite.json 2>/dev/null | head -n1 | xargs -r -I{} sh -c 'echo "TRI -> {}"; sed -n "1,120p" "{}"'

run.kie:
\tIN=""
\tif [ -s data/kie/test_real.jsonl ]; then IN=data/kie/test_real.jsonl; \
\telif [ -s data/kie/test.jsonl ]; then IN=data/kie/test.jsonl; \
\telif [ -s fixtures/eval_set.jsonl ]; then \
\t  mkdir -p reports_auto/kie; \
\t  $(PY) - <<'PYX' < fixtures/eval_set.jsonl > reports_auto/kie/_from_fixtures.jsonl ; \
import sys, json
for ln in sys.stdin:
    o=json.loads(ln); e=o.get("email",{})
    t=(e.get("subject","") + "\\n" + e.get("body","")).strip()
    print(json.dumps({"text": t}, ensure_ascii=False))
PYX
\t  IN=reports_auto/kie/_from_fixtures.jsonl; \
\tfi; \
\tif [ -n "$$IN" ]; then \
\t  echo "[KIE] input: $$IN"; \
\t  $(PY) tools/kie/eval.py "$$IN" "reports_auto/kie/pred.jsonl" || true; \
\t  echo "[KIE] head:"; head -n 10 reports_auto/kie/pred.jsonl || true; \
\telse \
\t  echo "[KIE] no input file found"; \
\tfi

db.migrate:
\t$(PY) tools/db_migrate.py migrate

db.views:
\t$(PY) tools/db_migrate.py views

db.snapshot:
\t$(PY) tools/db_migrate.py snapshot

bundle.support:
\t$(PY) tools/support_bundle.py || true
\tbash tools/print_everything.sh || true

health: db.migrate db.views db.snapshot run.tri run.kie bundle.support
\t@echo "[SPAM]"; \
\tif [ -f reports_auto/prod_quick_report.md ]; then sed -n '1,20p' reports_auto/prod_quick_report.md; else echo "no spam report"; fi
