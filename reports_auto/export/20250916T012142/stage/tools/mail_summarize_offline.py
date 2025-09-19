#!/usr/bin/env python3
import argparse, re, sqlite3
from pathlib import Path
from email import policy
from email.parser import BytesParser
from html import unescape
import json

def table_exists(conn, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name=?", (name,)).fetchone()
    return bool(row)

def cols_of(conn, name: str) -> set:
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({name});")}
    except sqlite3.Error:
        return set()

def pick_source(conn):
    """
    優先用 view: mails_compat（理想輸出含 id/subject/raw_path）
    若缺欄位或 view 不存在，回退到 mails 表並動態挑選主鍵/欄位。
    回傳: (source_name, id_col, subj_col, raw_col)
    """
    if table_exists(conn, "mails_compat"):
        c = cols_of(conn, "mails_compat")
        idc = "id" if "id" in c else ("case_id" if "case_id" in c else ("mail_id" if "mail_id" in c else None))
        subj = "subject" if "subject" in c else None
        raw  = "raw_path" if "raw_path" in c else None
        if idc and subj is not None and raw is not None:
            return ("mails_compat", idc, subj, raw)
    # fallback → mails
    c = cols_of(conn, "mails")
    idc = next((x for x in ("id","case_id","mail_id") if x in c), None)
    subj = "subject" if "subject" in c else None
    raw  = "raw_path" if "raw_path" in c else None
    return ("mails", idc, subj, raw)

def ensure_summary_col(conn, source_tbl: str):
    # 一律把結果寫回 mails.summary_json；若沒此欄則新增
    if table_exists(conn, "mails"):
        c = cols_of(conn, "mails")
        if "summary_json" not in c:
            conn.execute("ALTER TABLE mails ADD COLUMN summary_json TEXT;")
            conn.commit()

def extract_text(p: Path) -> str:
    try:
        if not p or not p.exists() or p.is_dir(): return ""
        msg = BytesParser(policy=policy.default).parse(open(p,"rb"))
    except Exception:
        return ""
    parts=[]
    try:
        if msg.is_multipart():
            for part in msg.walk():
                ctype=(part.get_content_type() or "").lower()
                if ctype=="text/plain":
                    parts.append(part.get_content())
                elif ctype=="text/html" and not parts:
                    html = part.get_content()
                    parts.append(unescape(re.sub(r"<[^>]+>"," ", str(html))))
        else:
            payload = msg.get_content()
            if (msg.get_content_type() or "").lower()=="text/html":
                payload = unescape(re.sub(r"<[^>]+>"," ", str(payload)))
            parts.append(str(payload))
    except Exception:
        pass
    return "\n".join(x for x in parts if x).strip()

def summarize(text: str, subject: str) -> dict:
    text = (text or "").strip()
    subj = (subject or "").strip()
    if not text:
        return {"title": subj, "bullets": [], "confidence": 0.5, "mode": "extractive"}
    flat = re.sub(r"\s+", " ", text)
    sents = [s for s in re.split(r"[。.!?，,；;]\s*", flat) if s][:5]
    return {"title": subj, "bullets": sents, "confidence": 0.66, "mode": "extractive"}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db", default="db/sma.sqlite")
    ap.add_argument("--run-dir", default="")
    args=ap.parse_args()

    conn = sqlite3.connect(args.db)
    src, idc, subj, raw = pick_source(conn)
    ensure_summary_col(conn, src)

    if not idc:
        print("[WARN] no id/case_id/mail_id in mails/mails_compat — skip"); return

    q = f"SELECT {idc}{','+subj if subj else ''}{','+raw if raw else ''} FROM {src}"
    updated=0; skipped=0
    for row in conn.execute(q):
        rid     = row[0]
        subject = row[1] if subj else ""
        rawp    = row[2] if raw  else None
        body    = extract_text(Path(rawp)) if rawp else ""
        summ    = summarize(body, subject)
        if table_exists(conn, "mails"):
            conn.execute(f"UPDATE mails SET summary_json=? WHERE {idc}=?;", (json.dumps(summ, ensure_ascii=False), rid))
            updated += 1
        else:
            skipped += 1
    conn.commit(); conn.close()
    print(f"[OK] summarized={updated}, skipped={skipped}, id_col={idc}, source={src}")

if __name__ == "__main__":
    main()
