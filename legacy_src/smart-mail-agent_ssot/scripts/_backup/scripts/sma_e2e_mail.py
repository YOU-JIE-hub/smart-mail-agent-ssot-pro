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
                    __faq_res_action_type_apath = "send_faq_reply", str(f)
                    try:
                        action_type, apath = __faq_res_action_type_apath
                    except Exception:
                        action_type = getattr(__faq_res_action_type_apath, 'text', str(__faq_res_action_type_apath))
                        apath = getattr(__faq_res_action_type_apath, 'score', getattr(__faq_res_action_type_apath, 'confidence', None))

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
