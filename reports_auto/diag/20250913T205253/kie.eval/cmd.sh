
    IN="";
    [ -s data/kie/test_real.jsonl ] && IN=data/kie/test_real.jsonl || true;
    [ -z "$IN" ] && [ -s data/kie/test.jsonl ] && IN=data/kie/test.jsonl || true;
    if [ -z "$IN" ] && [ -s fixtures/eval_set.jsonl ]; then
      mkdir -p reports_auto/kie;
      python - <<PYX < fixtures/eval_set.jsonl > reports_auto/kie/_from_fixtures.jsonl
import sys, json
for ln in sys.stdin:
    try:
        o=json.loads(ln); e=o.get("email",{})
        t=(e.get("subject","") + "\n" + e.get("body","")).strip()
        print(json.dumps({"text": t}, ensure_ascii=False))
    except: pass
PYX
      IN=reports_auto/kie/_from_fixtures.jsonl;
    fi;
    [ -z "$IN" ] && echo "no input" && exit 0;
    OUT="reports_auto/kie/pred_${TS}.jsonl";
    python tools/kie/eval.py "$IN" "$OUT" || true;
    echo "$OUT" > "reports_auto/kie/_last_pred.txt"
  
