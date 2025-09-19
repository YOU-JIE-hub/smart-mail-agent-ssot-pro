# -*- coding: utf-8 -*-
import os, re, json, argparse, sqlite3, datetime, hashlib, email
from email import policy
from email.parser import BytesParser
from pathlib import Path

def read_inputs(inp: Path):
    if inp.is_dir():
        # EMLs
        for p in sorted(inp.glob("*.eml")):
            with open(p, "rb") as f:
                msg = BytesParser(policy=policy.default).parse(f)
            subj = msg.get('subject') or ""
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body += part.get_content()
            else:
                body = msg.get_content()
            yield {"id": p.name, "subject": subj, "text": body}
    else:
        # jsonl: {"text": "..."} 或 {"subject": "...", "text": "..."}
        for ln in inp.read_text("utf-8").splitlines():
            ln=ln.strip()
            if not ln: continue
            obj=json.loads(ln)
            obj.setdefault("id", hashlib.md5((obj.get("subject","")+obj.get("text","")).encode("utf-8")).hexdigest()[:12])
            yield obj

def load_json(p, default=None):
    try:
        return json.loads(Path(p).read_text("utf-8"))
    except Exception:
        return default if default is not None else {}

def spam_score(text):
    # 極簡規則備援（若無模型門檻）：URL大量、虛假得獎、USDT等
    score = 0.0
    bad_kw = ["http://", "https://", "USDT", "中獎", "點此領取", "unsubscribe", "free money"]
    for k in bad_kw:
        if k.lower() in text.lower():
            score += 0.2
    return min(score, 1.0)

def intent_rules(text):
    # 極簡規則打分（示意：與 v11c 同方向但簡版；正式以你 repo 規則替換）
    scores = {k:0.0 for k in ["報價","技術支援","投訴","規則詢問","資料異動","其他"]}
    t = text.lower()
    if any(k in t for k in ["quote","報價","價格","試算","tco","seats","sow"]): scores["報價"] += 0.8
    if any(k in t for k in ["錯誤","error","500","502","bug","on-call","支援","修復"]): scores["技術支援"] += 0.7
    if any(k in t for k in ["客訴","抱怨","不滿","投訴","申訴","refund","賠償"]): scores["投訴"] += 0.7
    if any(k in t for k in ["規則","條款","faq","說明","policy","rpo","rto","sla"]): scores["規則詢問"] += 0.6
    if any(k in t for k in ["異動","更名","統編","電話","address","diff","更新資料"]): scores["資料異動"] += 0.7
    # 其他：若無明顯信號
    if max(scores.values()) < 0.3:
        scores["其他"] = 0.5
    return scores

def kie_extract(text):
    out=[]
    # amount（簡化：貨幣 + 數字）
    for m in re.finditer(r'(?:nt\$|usd|us\$|ntd|twd|\$)\s?[\d,]+(?:\.\d+)?', text, flags=re.I):
        out.append({"label":"amount","text":m.group(0),"start":m.start(),"end":m.end()})
    # date_time（簡化）
    for m in re.finditer(r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b|\b\d{1,2}[/-]\d{1,2}\b', text):
        out.append({"label":"date_time","text":m.group(0),"start":m.start(),"end":m.end()})
    # env
    for kw in ["uat","prod","production","staging","測試","正式"]:
        for m in re.finditer(kw, text, flags=re.I):
            out.append({"label":"env","text":m.group(0),"start":m.start(),"end":m.end()})
    # SLA
    for m in re.finditer(r'\bsla\b', text, flags=re.I):
        out.append({"label":"sla","text":m.group(0),"start":m.start(),"end":m.end()})
    return out

def ensure_db(dbp: Path):
    conn = sqlite3.connect(dbp.as_posix())
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS messages(
      id TEXT PRIMARY KEY, subject TEXT, text TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS intent_preds(
      id TEXT, label TEXT, score REAL, PRIMARY KEY(id,label)
    );
    CREATE TABLE IF NOT EXISTS kie_spans(
      id TEXT, label TEXT, span TEXT, start INT, end INT
    );
    CREATE TABLE IF NOT EXISTS actions(
      id TEXT, action_type TEXT, payload TEXT
    );
    """)
    conn.commit()
    return conn

def log_ndjson(p: Path, obj):
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--db", dest="db", required=True)
    ap.add_argument("--pipeline-log", dest="plog", required=True)
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    rpa = out/"rpa_out"; rpa.mkdir(parents=True, exist_ok=True)
    plog = Path(args.plog); plog.parent.mkdir(parents=True, exist_ok=True)
    dbp = Path(args.db); dbp.parent.mkdir(parents=True, exist_ok=True)

    # 門檻/校準
    ens = load_json("artifacts_prod/ens_thresholds.json", {"spam":0.405})
    calib = load_json("artifacts_prod/intent_rules_calib_v11c.json", {})

    conn = ensure_db(dbp)
    cur = conn.cursor()

    summary = {"total":0,"spam":0,"non_spam":0,"by_intent":{}}
    for rec in read_inputs(inp):
        mid = rec["id"]; subj = rec.get("subject",""); text = rec.get("text","")
        now = datetime.datetime.utcnow().isoformat()
        cur.execute("INSERT OR REPLACE INTO messages(id,subject,text,created_at) VALUES(?,?,?,?)",
                    (mid, subj, text, now))
        # Spam
        sscore = spam_score(subj + "\n" + text)
        is_spam = sscore >= float(ens.get("spam",0.405))
        ev = {"type":"spam_decision","id":mid,"score":sscore,"threshold":ens.get("spam",0.405),"spam":is_spam}
        log_ndjson(plog, ev)
        summary["total"] += 1
        if is_spam:
            summary["spam"] += 1
            # 行為：隔離（不產其他動作）
            cur.execute("INSERT OR REPLACE INTO actions(id,action_type,payload) VALUES(?,?,?)",
                        (mid, "quarantine", json.dumps({"reason":"spam","score":sscore}, ensure_ascii=False)))
            continue
        summary["non_spam"] += 1

        # Intent
        scores = intent_rules(subj + "\n" + text)
        # 可加上 calib 對各類 bias/min_keep 的啟發式（此處簡化保留最高分）
        label = max(scores.items(), key=lambda x: x[1])[0]
        for k,v in scores.items():
            cur.execute("INSERT OR REPLACE INTO intent_preds(id,label,score) VALUES(?,?,?)",(mid,k,float(v)))
        log_ndjson(plog, {"type":"intent","id":mid,"scores":scores,"label":label})
        summary["by_intent"][label] = summary["by_intent"].get(label,0)+1

        # KIE
        spans = kie_extract(subj + "\n" + text)
        for sp in spans:
            cur.execute("INSERT INTO kie_spans(id,label,span,start,end) VALUES(?,?,?,?,?)",
                        (mid, sp["label"], sp["text"], sp["start"], sp["end"]))
        log_ndjson(plog, {"type":"kie","id":mid,"spans":spans})

        # RPA（依意圖）
        if label=="技術支援":
            payload={"title": subj or "技術支援來信", "desc": text[:500]}
            (rpa/"tickets"/f"{mid}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
            cur.execute("INSERT OR REPLACE INTO actions(id,action_type,payload) VALUES(?,?,?)",(mid,"create_ticket",json.dumps(payload,ensure_ascii=False)))
        elif label=="資料異動":
            payload={"fields_detected":["company","tax_id","phone"],"diff":"(demo) 請審核"}
            (rpa/"diffs"/f"{mid}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
            cur.execute("INSERT OR REPLACE INTO actions(id,action_type,payload) VALUES(?,?,?)",(mid,"prepare_diff",json.dumps(payload,ensure_ascii=False)))
        elif label=="規則詢問":
            payload={"reply":"(demo) 您好，關於 SLA/RPO/RTO，附件說明..."}
            (rpa/"faq_replies"/f"{mid}.txt").write_text(payload["reply"], "utf-8")
            cur.execute("INSERT OR REPLACE INTO actions(id,action_type,payload) VALUES(?,?,?)",(mid,"faq_reply",json.dumps(payload,ensure_ascii=False)))
        elif label=="報價":
            html=f"<html><body><h3>報價草稿</h3><p>依需求試算，總額(示意) …</p></body></html>"
            (rpa/"quotes"/f"{mid}.html").write_text(html, "utf-8")
            cur.execute("INSERT OR REPLACE INTO actions(id,action_type,payload) VALUES(?,?,?)",(mid,"draft_quote",json.dumps({"html":True},ensure_ascii=False)))
        else:  # 其他/投訴：示意寄出回覆草稿
            payload={"to":"customer@example.com","subject":"我們已收到您的來信","body":"(demo) 我們會盡速回覆"}
            (rpa/"email_outbox"/f"{mid}.eml").write_text(f"Subject: {payload['subject']}\n\n{payload['body']}", "utf-8")
            cur.execute("INSERT OR REPLACE INTO actions(id,action_type,payload) VALUES(?,?,?)",(mid,"email_draft",json.dumps(payload,ensure_ascii=False)))

    conn.commit()
    # SUMMARY
    lines = ["# E2E SUMMARY", "", f"- total: {summary['total']}", f"- spam: {summary['spam']}", f"- non_spam: {summary['non_spam']}", "", "## by intent"]
    for k,v in sorted(summary["by_intent"].items(), key=lambda x:-x[1]):
        lines.append(f"- {k}: {v}")
    (Path(args.out)/"SUMMARY.md").write_text("\n".join(lines), "utf-8")
