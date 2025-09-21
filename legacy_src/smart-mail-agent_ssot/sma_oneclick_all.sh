#!/usr/bin/env bash
set -Eeuo pipefail
set -o pipefail
set +H

WIN_UNC='\\wsl.localhost\Ubuntu-22.04\home\youjie\projects\smart-mail-agent_ssot'
LINUX_ROOT="/home/youjie/projects/smart-mail-agent_ssot"
ROOT="${SMA_ROOT:-$LINUX_ROOT}"
if [[ ! -d "$ROOT" ]] && command -v wslpath >/dev/null 2>&1; then
  ROOT="$(wslpath -u "$WIN_UNC" 2>/dev/null || echo "$LINUX_ROOT")"
fi
cd "$ROOT" 2>/dev/null || { echo "[FATAL] 專案目錄不存在：$ROOT"; exit 2; }

TS="$(date +%Y%m%dT%H%M%S)"
mkdir -p reports_auto/logs reports_auto/status reports_auto/e2e_mail artifacts_inbox db scripts src/smart_mail_agent .github/workflows
RUN_LOG="reports_auto/logs/ONECLICK_${TS}.log"
ERR_LOG="reports_auto/logs/ONECLICK_ERROR_${TS}.log"
STATUS_MD="reports_auto/status/ONECLICK_${TS}.md"
PY_ERR="reports_auto/logs/E2E_${TS}.stderr.log"

FAILED_CMD=""
run_cmd(){ FAILED_CMD="$*"; "$@"; }

on_err(){
  ec=$?
  set +e
  {
    echo "----- ONECLICK FAILED -----"
    echo "time: $(date -Is)"
    echo "exit: $ec"
    echo "failed_cmd: ${FAILED_CMD:-<unknown>}"
    echo "pwd: $(pwd)"
    echo "ROOT: $ROOT"
    if [[ -s "$PY_ERR" ]]; then
      echo "--- python_stderr_head ---"; head -n 60 "$PY_ERR"
      echo "--- python_stderr_tail ---"; tail -n 60 "$PY_ERR"
    fi
  } | tee -a "$ERR_LOG"
  echo "[HINT] 詳情已寫入：$ERR_LOG" | tee -a "$RUN_LOG"
  exit "$ec"
}
set -o errtrace
trap on_err ERR
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$RUN_LOG"; }

[[ -f pyproject.toml ]] || cat > pyproject.toml <<'PY'
[project]
name = "smart-mail-agent"
version = "0.0.1"
description = "Smart Mail Agent — Spam/Intent/KIE → RPA E2E pipeline"
readme = "README.md"
requires-python = ">=3.10"
dependencies = []
[build-system]
requires = ["setuptools>=67"]
build-backend = "setuptools.build_meta"
PY
[[ -f README.md ]] || echo -e "# Smart-Mail-Agent\n使用：\`bash sma_oneclick_all.sh\`" > README.md
[[ -f pytest.ini ]] || echo -e "[pytest]\naddopts = -q" > pytest.ini
[[ -f .github/workflows/ci.yml ]] || cat > .github/workflows/ci.yml <<'YAML'
name: CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - run: python -m compileall src
YAML

log "Phase 1: 模型檢查與匯入"
NEEDED="reports_auto/status/NEEDED_${TS}.txt"; :> "$NEEDED"

if [[ ! -f artifacts_prod/model_pipeline.pkl || ! -f artifacts_prod/ens_thresholds.json ]]; then
  log "Spam 缺少產物，嘗試從 artifacts_inbox 解壓"
  mkdir -p artifacts_prod
  if command -v unzip >/dev/null 2>&1 && [[ -f artifacts_inbox/spam.zip ]]; then
    run_cmd unzip -oq artifacts_inbox/spam.zip -d artifacts_prod
    log "已解壓 spam.zip → artifacts_prod/"
  else
    echo "缺：artifacts_prod/model_pipeline.pkl, artifacts_prod/ens_thresholds.json" >> "$NEEDED"
  fi
else
  log "Spam 產物存在"
fi

if [[ ! -f artifacts/intent_pro_cal.pkl || ! -f reports_auto/intent_thresholds.json ]]; then
  log "Intent 缺少產物，嘗試從 artifacts_inbox 解壓"
  mkdir -p artifacts reports_auto
  if command -v unzip >/dev/null 2>&1 && [[ -f artifacts_inbox/intent.zip ]]; then
    run_cmd unzip -oq artifacts_inbox/intent.zip -d .
    log "已解壓 intent.zip"
  else
    echo "缺：artifacts/intent_pro_cal.pkl, reports_auto/intent_thresholds.json" >> "$NEEDED"
  fi
else
  log "Intent 產物存在"
fi

KIE_OK=0
if [[ -d kie && -f kie/config.json ]]; then
  KIE_OK=1
elif [[ -d artifacts_inbox/kie/kie && -f artifacts_inbox/kie/kie/config.json ]]; then
  rm -rf kie; mkdir -p kie; run_cmd cp -a artifacts_inbox/kie/kie/. kie/
  KIE_OK=1
elif command -v unzip >/dev/null 2>&1 && compgen -G "artifacts_inbox/kie_min_bundle_*.zip" >/dev/null; then
  ZIP_KIE="$(ls -1 artifacts_inbox/kie_min_bundle_*.zip | head -n1)"
  rm -rf kie; mkdir -p kie
  run_cmd unzip -oq "$ZIP_KIE" -d kie
  KIE_OK=1
fi
[[ $KIE_OK -eq 1 ]] && log "KIE 產物就位" || echo "缺：kie/ 或 artifacts_inbox/kie/kie/ 或 kie_min_bundle_*.zip" >> "$NEEDED"

log "Phase 2: 啟動虛擬環境與最小套件"
VENV=".venv"; [[ -x "$VENV/bin/python" ]] || run_cmd python3 -m venv "$VENV"
. "$VENV/bin/activate"
run_cmd python -m pip -q install -U pip
run_cmd pip -q install "joblib>=1.3" "numpy>=1.23" "scikit-learn==1.7.1" "pandas>=1.5,<3"

log "Phase 3: 產生 E2E 腳本（含 DB 自動遷移）"
cat > scripts/sma_e2e_mail.py <<'PY'
#!/usr/bin/env python3
# 讀取 .eml → Spam → Intent → KIE → RPA 產物；含 SQLite 自動遷移
import sys, os, re, json, time, sqlite3, uuid, traceback
from pathlib import Path
from datetime import datetime
from email import policy
from email.parser import BytesParser

ROOT = os.getenv("SMA_ROOT", os.path.expanduser("~/projects/smart-mail-agent_ssot"))
OUT_ROOT = os.path.join(ROOT, "reports_auto")
LOG_PATH = os.path.join(OUT_ROOT, "logs", "pipeline.ndjson")
DB_PATH = os.path.join(ROOT, "db", "sma.sqlite")

def log_event(kind, **payload):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    payload.update({"ts": datetime.utcnow().isoformat(timespec="seconds")+"Z", "kind": kind})
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

def ensure_db_and_migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 建表（若不存在）；注意使用引號避免關鍵字衝突
    cur.execute("""CREATE TABLE IF NOT EXISTS actions (
        id TEXT PRIMARY KEY, case_id TEXT, action_type TEXT, path TEXT, created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS intent_preds (
        case_id TEXT PRIMARY KEY, label TEXT, confidence REAL, created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS kie_spans (
        case_id TEXT, "key" TEXT, value TEXT, start INT, "end" INT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS err_log (
        ts TEXT, case_id TEXT, err TEXT
    )""")
    conn.commit()

    def ensure_column(table, col, ddl):
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
            log_event("db_migration_add_column", table=table, column=col, ddl=ddl)

    # 逐欄位補齊既有舊表
    ensure_column("kie_spans", "case_id", "case_id TEXT")
    ensure_column("kie_spans", "key", "\"key\" TEXT")
    ensure_column("kie_spans", "value", "value TEXT")
    ensure_column("kie_spans", "start", "start INT")
    ensure_column("kie_spans", "end", "\"end\" INT")
    ensure_column("err_log", "ts", "ts TEXT")
    ensure_column("err_log", "case_id", "case_id TEXT")
    ensure_column("err_log", "err", "err TEXT")

    conn.commit()
    conn.close()

def parse_eml(p: Path):
    with open(p, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    subject = msg["subject"] or ""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_content(); break
    else:
        body = msg.get_content()
    text = f"{subject}\n{body}"
    return subject, body, text

SPAM_HINTS = ["unsubscribe", "點此", "點擊這裡", "限時優惠", "中獎", "免費", "保證", "bitcoin", "比特幣"]

def load_spam():
    mp = os.path.join(ROOT, "artifacts_prod", "model_pipeline.pkl")
    thp = os.path.join(ROOT, "artifacts_prod", "ens_thresholds.json")
    if os.path.exists(mp) and os.path.exists(thp):
        try:
            import joblib
            model = joblib.load(mp)
            with open(thp, "r", encoding="utf-8") as f:
                th = json.load(f)
            thresh = float(th.get("spam", 0.5))
            return ("real", model, thresh)
        except Exception as e:
            log_event("warn", component="spam_loader", error=repr(e))
    return ("stub", None, 0.6)

def spam_predict(text, ctx):
    mode, model, thresh = ctx
    if mode == "real":
        try:
            prob = float(model.predict_proba([text])[0][-1])
            return (prob >= thresh, prob)
        except Exception as e:
            log_event("warn", component="spam_infer", error=repr(e))
    lower = text.lower()
    score = sum(1 for k in SPAM_HINTS if k in lower)
    conf = min(0.2 + 0.35 * score, 0.99)
    return (score >= 2, conf)

INTENT_LABELS = ["報價", "技術支援", "投訴", "規則詢問", "資料異動", "其他"]

def load_intent():
    mp = os.path.join(ROOT, "artifacts", "intent_pro_cal.pkl")
    thp = os.path.join(ROOT, "reports_auto", "intent_thresholds.json")
    model, lbls, th_map = None, INTENT_LABELS, {}
    mode = "stub"
    if os.path.exists(mp):
        try:
            import joblib, numpy as np  # noqa
            model = joblib.load(mp)
            lbls = getattr(model, "classes_", INTENT_LABELS)
            mode = "real"
        except Exception as e:
            log_event("warn", component="intent_loader", error=repr(e))
            model = None; mode = "stub"
    if os.path.exists(thp):
        try:
            with open(thp, "r", encoding="utf-8") as f:
                th_map = json.load(f)
        except Exception as e:
            log_event("warn", component="intent_thresholds", error=repr(e))
    return (mode, model, list(lbls), th_map)

def intent_predict(text, ctx):
    mode, model, lbls, th_map = ctx
    if mode == "real" and model is not None:
        try:
            import numpy as np
            probs = model.predict_proba([text])[0]
            i = int(np.argmax(probs))
            label = str(lbls[i]); conf = float(probs[i])
            min_th = float(th_map.get(label, 0.5))
            low_conf = conf < min_th
            return (label, conf, low_conf)
        except Exception as e:
            log_event("warn", component="intent_infer", error=repr(e))
    rules = {
        "報價": ["報價", "quote", "報價單", "價格", "估價"],
        "技術支援": ["無法登入", "錯誤", "bug", "error", "支援", "故障"],
        "投訴": ["抱怨", "投訴", "不滿", "客訴"],
        "規則詢問": ["如何", "可否", "流程", "規則", "policy", "條款", "FAQ", "faq"],
        "資料異動": ["變更", "更新資料", "修改地址", "電話變更", "個資"],
    }
    for k, kws in rules.items():
        if any(kw.lower() in text.lower() for kw in kws):
            return (k, 0.85, False)
    return ("其他", 0.35, False)

def kie_extract(text: str):
    spans = []
    m = re.search(r"(20\d{2}[-/\.](0?[1-9]|1[0-2])[-/\.](0?[1-9]|[12]\d|3[01]))", text)
    if m: spans.append(("date_time", m.group(1), m.start(), m.end()))
    m = re.search(r"(NTD|NT\$|\$)\s?([0-9]{1,3}(,[0-9]{3})*(\.[0-9]+)?|[0-9]+(\.[0-9]+)?)", text)
    if m: spans.append(("amount", m.group(0), m.start(), m.end()))
    for env in ["prod", "staging", "dev", "UAT", "uat"]:
        i = text.lower().find(env.lower())
        if i >= 0: spans.append(("env", env, i, i+len(env)))
    m = re.search(r"(\d+)\s*(hours|hrs|days|天|小時)", text, re.I)
    if m: spans.append(("sla", m.group(0), m.start(), m.end()))
    return spans

def main():
    if len(sys.argv) < 2:
        print("Usage: sma_e2e_mail.py <eml_dir>", file=sys.stderr); sys.exit(2)
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"[FATAL] not found: {src}", file=sys.stderr); sys.exit(2)

    ensure_db_and_migrate()
    ts = time.strftime("%Y%m%dT%H%M%S")
    run_dir = Path(OUT_ROOT) / "e2e_mail" / ts
    rpa = run_dir / "rpa_out"
    for d in ["email_outbox", "tickets", "diffs", "faq_replies", "quotes", "manual_queue", "errors"]:
        (rpa / d).mkdir(parents=True, exist_ok=True)

    cases_fp = open(run_dir / "cases.jsonl", "w", encoding="utf-8")
    actions_fp = open(run_dir / "actions.jsonl", "w", encoding="utf-8")
    plan_fp = open(run_dir / "actions_plan.ndjson", "w", encoding="utf-8")
    summary = {"total": 0, "spam": 0, "ham": 0, "by_intent": {}}

    spam_ctx = load_spam()
    intent_ctx = load_intent()
    kie_present = os.path.exists(os.path.join(ROOT, "kie", "config.json"))
    log_event("startup", spam_mode=spam_ctx[0], intent_mode=intent_ctx[0], kie_present=bool(kie_present), eml_dir=str(src))

    conn = sqlite3.connect(DB_PATH); cur = conn.cursor()
    for eml in src.glob("**/*.eml"):
        summary["total"] += 1
        case_id = str(uuid.uuid4())
        try:
            subject, body, text = parse_eml(eml)

            is_spam, sconf = spam_predict(text, spam_ctx)
            if is_spam:
                summary["spam"] += 1
                action = {"id": str(uuid.uuid4()), "case_id": case_id, "action_type": "quarantine", "path": str(eml)}
                actions_fp.write(json.dumps(action, ensure_ascii=False)+"\n")
                cur.execute("INSERT OR REPLACE INTO intent_preds(case_id,label,confidence,created_at) VALUES(?,?,?,?)",
                            (case_id, "N/A", 0.0, datetime.utcnow().isoformat()+"Z"))
                log_event("quarantine", case_id=case_id, eml=str(eml), spam_conf=float(sconf))
                label, iconf = "N/A", 0.0
            else:
                summary["ham"] += 1
                label, iconf, low = intent_predict(text, intent_ctx)
                summary["by_intent"][label] = summary["by_intent"].get(label, 0) + 1

                if low:
                    mpath = rpa / "manual_queue" / f"{case_id}.txt"
                    mpath.write_text("低信心樣本，請人工複核", encoding="utf-8")
                    action_type, apath = "manual_review", str(mpath)
                elif label == "報價":
                    q = rpa / "quotes" / f"{case_id}.html"
                    q.write_text(f"<html><body><h1>報價單</h1><p>Subject: {subject}</p></body></html>", encoding="utf-8")
                    action_type, apath = "make_quote", str(q)
                elif label == "技術支援":
                    t = rpa / "tickets" / f"{case_id}.json"
                    t.write_text(json.dumps({"subject": subject, "desc": body}, ensure_ascii=False, indent=2), encoding="utf-8")
                    action_type, apath = "create_ticket", str(t)
                elif label == "規則詢問":
                    f = rpa / "faq_replies" / f"{case_id}.txt"
                    f.write_text("感謝來信，以下為常見問題的說明。", encoding="utf-8")
                    action_type, apath = "send_faq_reply", str(f)
                elif label == "資料異動":
                    d = rpa / "diffs" / f"{case_id}.json"
                    d.write_text(json.dumps({"diff": "請填入實際比對結果"}, ensure_ascii=False), encoding="utf-8")
                    action_type, apath = "generate_diff", str(d)
                else:
                    out = rpa / "email_outbox" / f"{case_id}.txt"
                    out.write_text("感謝您的來信，我們已收到。", encoding="utf-8")
                    action_type, apath = "prepare_reply", str(out)

                actions_fp.write(json.dumps({"id": str(uuid.uuid4()), "case_id": case_id, "action_type": action_type, "path": apath}, ensure_ascii=False)+"\n")

                for k,v,s,e in kie_extract(text):
                    # 使用引號避免 'key'、'end' 字樣造成兼容性問題
                    cur.execute('INSERT INTO kie_spans(case_id,"key",value,start,"end") VALUES(?,?,?,?,?)', (case_id,k,v,s,e))

                cur.execute("INSERT OR REPLACE INTO intent_preds(case_id,label,confidence,created_at) VALUES(?,?,?,?)",
                            (case_id, label, float(iconf), datetime.utcnow().isoformat()+"Z"))
                log_event("e2e_case", case_id=case_id, intent=label, intent_conf=float(iconf), path=apath)

            case = {"id": case_id, "subject": subject, "spam": bool(is_spam), "spam_conf": float(sconf), "intent": label, "intent_conf": float(iconf)}
            (run_dir / "cases.jsonl").open("a", encoding="utf-8").write(json.dumps(case, ensure_ascii=False)+"\n")

        except Exception as e:
            cur.execute("INSERT INTO err_log(ts,case_id,err) VALUES(?,?,?)",
                        (datetime.utcnow().isoformat()+"Z", case_id, repr(e)))
            (rpa / "errors" / f"{case_id}.err").write_text(traceback.format_exc(), encoding="utf-8")
            log_event("error", case_id=case_id, error=repr(e))

    conn.commit(); conn.close()
    cases_fp.close(); actions_fp.close(); plan_fp.close()

    s_md = [f"# E2E Summary ({ts})",
            f"- Total: {summary['total']}",
            f"- Spam: {summary['spam']}",
            f"- Ham: {summary['ham']}",
            "## By Intent"]
    for k,v in summary["by_intent"].items():
        s_md.append(f"- {k}: {v}")
    (run_dir / "SUMMARY.md").write_text("\n".join(s_md), encoding="utf-8")
    print(f"[OK] E2E 完成 → {run_dir}")
if __name__ == "__main__":
    main()
PY
chmod +x scripts/sma_e2e_mail.py

# 準備 demo .eml（若缺）
if [[ ! -d data/demo_eml ]]; then
  mkdir -p data/demo_eml
  cat > data/demo_eml/sample_quote.eml <<'EML'
From: demo@example.com
To: you@example.com
Subject: 需要報價 2025-09-06

您好，請問這個方案報價是多少？可否提供正式報價單？我們期望 7 天內完成。
EML
fi

# 執行 E2E；同時收集 stderr
VENV=".venv"; [ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
. "$VENV/bin/activate"
run_cmd python scripts/sma_e2e_mail.py "data/demo_eml" \
  1> >(tee -a "$RUN_LOG") \
  2> >(tee -a "$PY_ERR" >&2)

# 狀態摘要
{
  echo "# ONECLICK 狀態"
  echo "ROOT: ${ROOT}"
  echo "RUN_LOG: ${RUN_LOG}"
  echo "ERR_LOG: ${ERR_LOG}"
  echo "PY_ERR: ${PY_ERR}"
  latest="$(ls -1dt reports_auto/e2e_mail/* 2>/dev/null | head -n1 || true)"
  echo "run_dir: ${latest:-<none>}"
  echo "sqlite: db/sma.sqlite"
  echo "pipeline.ndjson: reports_auto/logs/pipeline.ndjson"
} | tee "$STATUS_MD"

echo "[OK] 全流程完成"

# Reroute post-step (guarded)
if [ "${SMA_INTENT_RULES:-1}" = "1" ]; then
  python scripts/sma_reroute_last_run_intent.py || true
fi

