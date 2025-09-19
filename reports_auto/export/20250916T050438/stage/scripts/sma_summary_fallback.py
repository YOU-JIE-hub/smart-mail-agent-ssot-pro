#!/usr/bin/env python3
import sys, os, json, sqlite3, time
from pathlib import Path

def count_dir(p: Path) -> int:
    return sum(1 for _ in p.glob("*")) if p.is_dir() else 0

def main():
    if len(sys.argv) < 2:
        print("usage: sma_summary_fallback.py <OUT_DIR>")
        sys.exit(1)
    out_dir = Path(sys.argv[1]); out_dir.mkdir(parents=True, exist_ok=True)
    db_path = os.environ.get("SMA_DB_PATH", "db/sma.sqlite")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    # 粗略統計：rpa_out 產物與 DB 行數（若可讀）
    rpa = out_dir / "rpa_out"
    stats = {
        "tickets": count_dir(rpa / "tickets"),
        "email_outbox": count_dir(rpa / "email_outbox"),
        "diffs": count_dir(rpa / "diffs"),
        "faq_replies": count_dir(rpa / "faq_replies"),
        "quotes": count_dir(rpa / "quotes"),
    }
    db_rows = {}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        for t in ["mails","intent_preds","kie_spans","actions","approvals","err_log","llm_calls"]:
            try:
                cur.execute(f"SELECT COUNT(1) FROM {t}")
                db_rows[t] = int(cur.fetchone()[0])
            except Exception:
                pass
        conn.close()
    except Exception:
        pass

    md = []
    md.append(f"# SUMMARY（fallback） @ {ts}\n")
    md.append("此檔案為備援生成，正式 SUMMARY 由 e2e 產生。\n")
    md.append("## RPA 產物計數\n")
    for k, v in stats.items():
        md.append(f"- {k}: {v}")
    md.append("\n## DB 行數\n")
    for k, v in db_rows.items():
        md.append(f"- {k}: {v}")
    md.append("\n## 提示\n- 若你期待正式 SUMMARY，請檢查 `src/smart_mail_agent/cli/e2e.py` 與其參數是否一致。")
    (out_dir / "SUMMARY.md").write_text("\n".join(md), encoding="utf-8")
    # 也輸出一個空 actions 檔，避免下游找不到
    (out_dir / "actions.jsonl").write_text("", encoding="utf-8")
    print(f"[OK] fallback SUMMARY written => {out_dir/'SUMMARY.md'}")

if __name__ == "__main__":
    main()
