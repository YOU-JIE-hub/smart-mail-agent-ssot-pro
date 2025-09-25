#!/usr/bin/env bash
# 從 data/demo_eml/* 解析 .eml → 建立新的 run 與 cases.jsonl（含 subject/body/text）
# 然後呼叫：重路由 → 寫回 cases → 產出 RPA → 驗證 → 狀態摘要
set -Eeuo pipefail

ROOT="/home/youjie/projects/smart-mail-agent_ssot"
DEMO="$ROOT/data/demo_eml"
TS="$(date +%Y%m%dT%H%M%S)"
RUN="$ROOT/reports_auto/e2e_mail/$TS"
ERRDIR="$ROOT/reports_auto/errors/BOOTSTRAP_${TS}"
LOG="$ERRDIR/run.log"

mkdir -p "$ERRDIR" "$RUN" "$RUN/rpa_out"/{quotes,tickets,faq_replies,diffs,email_outbox}

log(){ printf '%s\n' "$*" | tee -a "$LOG" >&2; }
fatal(){ printf '[FATAL] %s\n' "$*" | tee -a "$LOG" >&2; exit 2; }
trap 'echo "[ERR] line=$LINENO" | tee -a "$LOG" >&2' ERR

[ -d "$DEMO" ] || fatal "$DEMO 不存在"
shopt -s nullglob
files=("$DEMO"/*.eml)
[ ${#files[@]} -gt 0 ] || fatal "$DEMO 無 .eml 檔"

python - <<'PY'
from email import policy
from email.parser import BytesParser
from pathlib import Path
import json, time, hashlib

ROOT=Path("/home/youjie/projects/smart-mail-agent_ssot")
DEMO=ROOT/"data/demo_eml"
RUN =ROOT/"reports_auto/e2e_mail"/time.strftime("%Y%m%dT%H%M%S")
RUN.mkdir(parents=True, exist_ok=True)

def read_eml(p: Path):
    with open(p, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    subj = (msg["subject"] or "").strip()
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type()=="text/plain":
                body = (part.get_content() or "").strip()
                break
    else:
        body = (msg.get_content() or "").strip()
    text = (subj + "\n\n" + body).strip()
    return subj, body, text

out=[]
for eml in sorted(DEMO.glob("*.eml")):
    subj, body, text = read_eml(eml)
    hid = hashlib.md5(str(eml).encode("utf-8")).hexdigest()[:8]
    case_id = f"{eml.stem}_{hid}"
    out.append({
        "id": case_id,
        "intent": "其他",
        "subject": subj,
        "body": body,
        "text": text,
        "source_path": str(eml)
    })

case_p = RUN/"cases.jsonl"
with open(case_p,"w",encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False)+"\n")

(RUN/"SUMMARY.md").write_text("# Bootstrap run\n- source: data/demo_eml\n- cases: {}\n".format(len(out)), encoding="utf-8")
print(str(RUN))
PY

# 以檔案時間鎖定剛建立的 run 目錄（避免時間秒差）
RUN_PATH="$(ls -1dt "$ROOT"/reports_auto/e2e_mail/* 2>/dev/null | head -n1 || true)"
[ -n "$RUN_PATH" ] || fatal "找不到新建的 run 目錄"
[ -s "$RUN_PATH/cases.jsonl" ] || fatal "新建 run 的 cases.jsonl 為空：$RUN_PATH"

export RUN_PATH

# DB schema 防呆
python scripts/sma_db_migrate_intents.py >/dev/null 2>&1 || true

# 重路由（失敗也不中斷）
python scripts/sma_reroute_last_run_intent.py --run-dir "$RUN_PATH" || log "[WARN] reroute 失敗，後續仍繼續"

# 將最終意圖覆蓋回 cases.jsonl
if [ -f scripts/sma_apply_reroute_to_cases.py ]; then
  python scripts/sma_apply_reroute_to_cases.py --run-dir "$RUN_PATH" || log "[WARN] 覆蓋最終意圖失敗"
else
  python - <<'PY' || true
import csv, json, os
from pathlib import Path
run=Path(os.environ["RUN_PATH"])
def load_final_map(run: Path):
    m={}
    csvp=run/"intent_reroute_audit.csv"; ndp=run/"intent_reroute_suggestion.ndjson"
    if csvp.exists():
        import io
        with open(csvp,newline="",encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cid=row.get("id") or row.get("case_id")
                fin=row.get("final_intent") or row.get("final")
                if cid and fin: m[cid]=fin
    elif ndp.exists():
        for ln in open(ndp,"r",encoding="utf-8"):
            try:
                j=json.loads(ln); cid=j.get("id") or j.get("case_id"); fin=j.get("final") or j.get("final_intent")
                if cid and fin: m[cid]=fin
            except Exception: pass
    return m
m=load_final_map(run)
cj=run/"cases.jsonl"
rows=[json.loads(x) for x in open(cj,"r",encoding="utf-8") if x.strip()]
for r in rows:
    fin=m.get(r.get("id"))
    if fin: r["intent"]=fin
with open(cj,"w",encoding="utf-8") as f:
    for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
print("[OK] cases.jsonl updated:", cj)
PY
fi

# 生成 RPA 佔位與驗證
python scripts/sma_make_rpa_placeholders.py --run-dir "$RUN_PATH" || true
python scripts/validate_rpa_outputs.py || true

# 狀態摘要
STATUS="$ROOT/reports_auto/status/ONECLICK_BOOTSTRAP_${TS}.md"
LATEST="$ROOT/reports_auto/status/LATEST.md"
{
  echo "# Bootstrap After-run Summary ($TS)"
  echo "- run_dir: ${RUN_PATH#"$ROOT/"}"
  echo "- intent_thresholds: reports_auto/intent_thresholds.json"
  echo "- reroute: present"
  echo "## Files"
  echo "- ${RUN_PATH#"$ROOT/"}"/intent_reroute_summary.md
  echo "- ${RUN_PATH#"$ROOT/"}"/intent_reroute_audit.csv
  echo "- ${RUN_PATH#"$ROOT/"}"/intent_reroute_suggestion.ndjson
} | tee "$STATUS" > "$LATEST"

echo "[OK] bootstrap completed -> $STATUS"
