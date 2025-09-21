#!/usr/bin/env bash
set -Eeuo pipefail
INFER_IN="${INFER_IN:-data/intent/external_realistic_test.clean.jsonl}"
MIN_PROB="${MIN_PROB:-0.25}"
KIE_KEEP="${KIE_KEEP:-amount,env,sla,date_time}"
FUZZY_TH="${FUZZY_TH:-0.90}"
SPAM_BETA="${SPAM_BETA:-2.0}"
ROOT="${ROOT:-$HOME/projects/smart-mail-agent_ssot}"; cd "$ROOT" || exit 2
[[ -d .venv ]] || python3 -m venv .venv; . .venv/bin/activate 2>/dev/null || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:.sma_tools:${PYTHONPATH:-}" TOKENIZERS_PARALLELISM=false
mkdir -p reports_auto/{logs,status,alignment,silver,diagnostics} data/spam
TS="$(date +%Y%m%dT%H%M%S)"; LOG="reports_auto/logs/oneclick_all_${TS}.log"
ln -sf "$(basename "$LOG")" reports_auto/logs/latest.log || true
exec > >(stdbuf -oL -eL tee -a "$LOG") 2>&1
trap 'ec=$?; echo; echo "[ERROR] exit=$ec line:$LINENO cmd:${BASH_COMMAND}"; tail -n 200 "$LOG" > "reports_auto/diagnostics/LAST_TAIL_${TS}.log" || true; printf "exit=%s\ncmd=%s\n" "$ec" "${BASH_COMMAND}" > "reports_auto/diagnostics/LAST_CAUSE_${TS}.txt"; exit $ec' ERR
echo "[STEP] CRLF 清理"
shopt -s nullglob; for p in "$INFER_IN" reports_auto/predict_all.jsonl data/intent/*.jsonl data/spam/*.jsonl; do [[ -f "$p" ]] && sed -i 's/\r$//' "$p"; done; shopt -u nullglob
echo "[STEP] 正規化輸入：$INFER_IN"
python .sma_tools/jsonl_doctor.py normalize -i "$INFER_IN" -o "$INFER_IN.tmp" && mv -f "$INFER_IN.tmp" "$INFER_IN"
echo "[STEP] 推理 → reports_auto/predict_all.jsonl"
python .sma_tools/sma_infer_all_three.py "$INFER_IN" --out reports_auto/predict_all.jsonl
python .sma_tools/jsonl_doctor.py normalize -i reports_auto/predict_all.jsonl -o reports_auto/predict_all.jsonl.tmp && mv -f reports_auto/predict_all.jsonl.tmp reports_auto/predict_all.jsonl
echo "[STEP] KIE 追加"
cp -f reports_auto/predict_all.jsonl reports_auto/predict_all.jsonl.kie_in
PYTHONPATH="src:.sma_tools" python .sma_tools/sma_kie_add.py --src "$INFER_IN" --pred_in reports_auto/predict_all.jsonl.kie_in --pred_out reports_auto/predict_all.jsonl --kie_dir artifacts_kie/model --chunk 4 --maxlen 512 --min_prob "$MIN_PROB" --keep_labels "$KIE_KEEP"
python .sma_tools/jsonl_doctor.py normalize -i reports_auto/predict_all.jsonl -o reports_auto/predict_all.jsonl.tmp && mv -f reports_auto/predict_all.jsonl.tmp reports_auto/predict_all.jsonl
echo "[STEP] KIE regex 補齊"
PYTHONPATH="src:.sma_tools" python .sma_tools/kie_regex_fill.py --src "$INFER_IN" --pred_in reports_auto/predict_all.jsonl --pred_out reports_auto/predict_all.jsonl.tmp
mv -f reports_auto/predict_all.jsonl.tmp reports_auto/predict_all.jsonl
python .sma_tools/jsonl_doctor.py normalize -i reports_auto/predict_all.jsonl -o reports_auto/predict_all.jsonl.tmp && mv -f reports_auto/predict_all.jsonl.tmp reports_auto/predict_all.jsonl
echo "[STEP] KIE 摘要"
python - <<'PY'
import json,collections
cnt=collections.Counter(); src=collections.Counter(); empt=0; n=0
for ln in open("reports_auto/predict_all.jsonl",encoding="utf-8"):
    if not ln.strip(): continue
    n+=1; o=json.loads(ln); spans=(o.get("kie") or {}).get("spans") or []
    if not spans: empt+=1
    for s in spans: cnt[s.get("label","_")]+=1; src[s.get("source","kie")]+=1
open("reports_auto/status/KIE_SUMMARY.txt","w",encoding="utf-8").write(f"[SUMMARY] TOTAL={n} EMPTY={empt} | LABEL={dict(cnt)} | SOURCE={dict(src)}\n")
print("[SUMMARY]",f"TOTAL={n} EMPTY={empt} | LABEL={dict(cnt)} | SOURCE={dict(src)}")
PY
echo "[STEP] 檢查/產生 Intent gold（.fixed）"
if [[ ! -f data/intent/test_labeled.fixed.jsonl && -f data/intent/test_labeled.jsonl ]]; then
  python .sma_tools/gold_fix_ids.py --in data/intent/test_labeled.jsonl --out data/intent/test_labeled.fixed.jsonl
fi
GOLD_INT=""; [[ -f data/intent/test_labeled.fixed.jsonl ]] && GOLD_INT="data/intent/test_labeled.fixed.jsonl" || GOLD_INT="data/intent/test_labeled.jsonl"
echo "[STEP] 對齊（不足即 fallback）"
python .sma_tools/align_gold_to_pred.py --gold "$GOLD_INT" --pred reports_auto/predict_all.jsonl --pred_text "$INFER_IN" --out reports_auto/alignment/gold2pred_intent.csv --mode auto --fuzzy_threshold "$FUZZY_TH"
python - <<'PY'
import re, pathlib
p=pathlib.Path("reports_auto/alignment/ALIGN_SUMMARY.txt"); cov=matched=total=0
if p.exists():
    s=p.read_text(encoding="utf-8")
    import re
    m=re.search(r"COVERAGE=([0-9.]+)",s); cov=float(m.group(1)) if m else 0.0
    m=re.search(r"MATCHED=(\d+)",s); matched=int(m.group(1)) if m else 0
    m=re.search(r"TOTAL_GOLD=(\d+)",s); total=int(m.group(1)) if m else 0
print(f"[ALIGN] gold={total} covered={matched} coverage={cov:.4f}")
PY
echo "[STEP] Intent 評估"
python .sma_tools/eval_intent_spam.py --task intent --gold "$GOLD_INT" --pred reports_auto/predict_all.jsonl --map reports_auto/alignment/gold2pred_intent.csv --out reports_auto/metrics_intent.txt
echo "[STEP] Spam gold 準備（若不存在則由 intent.fixed 轉 0/1）"
if [[ ! -f data/spam/test_labeled.jsonl && -f "$GOLD_INT" ]]; then
python - <<'PY'
import json, pathlib
src = pathlib.Path("data/intent/test_labeled.fixed.jsonl") if pathlib.Path("data/intent/test_labeled.fixed.jsonl").exists() else pathlib.Path("data/intent/test_labeled.jsonl")
dst = pathlib.Path("data/spam/test_labeled.jsonl"); dst.parent.mkdir(parents=True, exist_ok=True)
def to01(v):
    if isinstance(v,(int,float)): return 1 if int(v)==1 else 0
    s=str(v).strip().lower(); return 1 if s in ("1","true","spam") else 0
with src.open(encoding="utf-8",errors="ignore") as f, dst.open("w",encoding="utf-8") as g:
    for ln in f:
        if not ln.strip(): continue
        o=json.loads(ln); 
        if "label" in o: o["label"]=to01(o["label"])
        g.write(json.dumps(o,ensure_ascii=False)+"\n")
print(f"[SPAM_GOLD] wrote {dst}")
PY
fi
echo "[STEP] Spam 門檻校準（F-beta）"
python .sma_tools/spam_calibrate_threshold.py --gold data/spam/test_labeled.jsonl --pred reports_auto/predict_all.jsonl --map reports_auto/alignment/gold2pred_intent.csv --out reports_auto/status/SPAM_CALIBRATION.txt --beta "$SPAM_BETA"
echo "[STEP] 應用校準分數到 score_text"
python .sma_tools/spam_apply_calibration.py -i reports_auto/predict_all.jsonl -o reports_auto/predict_all.jsonl.tmp -c reports_auto/status/spam_calibration.json
mv -f reports_auto/predict_all.jsonl.tmp reports_auto/predict_all.jsonl
echo "[STEP] Spam 評估（使用校準門檻）"
THRESH="$(python - <<'PY'
import json,sys
try: print(json.load(open("reports_auto/status/spam_calibration.json"))["threshold"])
except: print(0.5)
PY
)"
python .sma_tools/eval_intent_spam.py --task spam --gold data/spam/test_labeled.jsonl --pred reports_auto/predict_all.jsonl --map reports_auto/alignment/gold2pred_intent.csv --out reports_auto/metrics_spam.txt --spam_threshold "$THRESH"
echo "[STEP] 銀標（identity）評估（若存在）"
if [[ -f reports_auto/silver/intent_silver.jsonl ]]; then
  python - <<'PY'
import json, csv, pathlib
inp = pathlib.Path("reports_auto/silver/intent_silver.jsonl")
out = pathlib.Path("reports_auto/alignment/gold2pred_intent_silver_identity.csv")
out.parent.mkdir(parents=True, exist_ok=True)
with inp.open(encoding="utf-8", errors="ignore") as f, out.open("w", encoding="utf-8", newline="") as g:
    w = csv.writer(g); w.writerow(["gold_id","pred_id","method","similarity"])
    for ln in f:
        if not ln.strip(): continue
        o=json.loads(ln); i=o.get("id")
        if i: w.writerow([i, i, "identity", "1.0000"])
print(f"[WRITE] {out}")
PY
  python .sma_tools/eval_intent_spam.py --task intent --gold reports_auto/silver/intent_silver.jsonl --pred reports_auto/predict_all.jsonl --map reports_auto/alignment/gold2pred_intent_silver_identity.csv --out reports_auto/metrics_intent_silver.txt
fi
echo "[STEP] 產出 ONECLICK 摘要"
SUM="reports_auto/status/ONECLICK_SUMMARY_${TS}.md"
{
  echo "# ONECLICK Summary"
  echo; echo "## Alignment"; sed -n '1,120p' reports_auto/alignment/ALIGN_SUMMARY.txt 2>/dev/null || true
  echo; echo "## KIE Summary"; sed -n '1,80p' reports_auto/status/KIE_SUMMARY.txt 2>/dev/null || true
  echo; echo "## Intent (gold)"; echo '```'; sed -n '1,160p' reports_auto/metrics_intent.txt 2>/dev/null; echo '```'
  if [[ -f reports_auto/metrics_intent_silver.txt ]]; then echo; echo "## Intent (silver/identity)"; echo '```'; sed -n '1,160p' reports_auto/metrics_intent_silver.txt; echo '```'; fi
  echo; echo "## Spam (calibrated)"; echo '```'; sed -n '1,160p' reports_auto/metrics_spam.txt 2>/dev/null; echo '```'
  echo; echo "_log: $(basename "$LOG")_"
} > "$SUM"
echo "[WRITE] $SUM"
echo "[DONE] oneclick_all_in_one (log: $LOG)"
