from __future__ import annotations
from pathlib import Path
import argparse, os

from smart_mail_agent.observability.ndjson_v1 import NDJSONLogger
from tools.rag_faq import search

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--kb-dir", default="kb/faq")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--ndjson")
    ap.add_argument("--min-score", type=float, default=None, help="最低相似度；預設取環境變數或 0.05")
    ap.add_argument("--force", action="store_true", help="無視分數也要內嵌 Top-1")
    a=ap.parse_args()

    rd=Path(a.run_dir)
    outbox=rd/"rpa_out"/"email_outbox"
    outbox.mkdir(parents=True, exist_ok=True)

    events=a.ndjson or f"reports_auto/events/{rd.name}.ndjson"
    logger=NDJSONLogger(events)

    force = a.force or (os.getenv("SMA_RAG_FORCE","0")=="1")
    min_score = a.min_score if a.min_score is not None else float(os.getenv("SMA_RAG_MIN_SCORE", "0.05"))

    changed=0
    for txt in sorted(outbox.glob("*.txt")):
        body=txt.read_text("utf-8", errors="ignore")
        subject=""; 
        for ln in body.splitlines():
            if ln.lower().startswith("subject:"):
                subject=ln.split(":",1)[1].strip(); break
        q=(subject+" "+body).strip()
        hits=search(q, a.kb_dir, a.topk)

        reason="hit"
        use_hits=[]
        if hits:
            if force or hits[0]["score"] >= min_score:
                use_hits = hits
                reason = "forced" if force and hits[0]["score"] < min_score else "hit"
            else:
                reason = "low_score"
        elif force:
            # 沒命中但強制：取 KB 目錄第一篇
            kb_list = sorted(Path(a.kb_dir).rglob("*.md")) + sorted(Path(a.kb_dir).rglob("*.txt"))
            if kb_list:
                use_hits = [{"file": kb_list[0].name, "title": kb_list[0].stem, "snippet": kb_list[0].read_text('utf-8', errors='ignore')[:240].replace("\n"," ")+"…", "score": 0.0}]
                reason = "forced_nohit"
            else:
                reason = "no_kb"

        if not use_hits:
            logger.write(action="faq_embed_skip", result="skip", idem=txt.stem, intent=None, err_type=reason)
            continue

        block=["","\n----- FAQ 建議回覆 (RAG) -----"]
        for i,h in enumerate(use_hits,1):
            block.append(f"{i}. {h.get('title','') or '(untitled)'} 〔{h.get('file','')}〕 score={h.get('score',0):.3f}")
            block.append(f"   {h.get('snippet','')}")
        block.append("----- End FAQ -----\n")
        txt.write_text(body + "\n" + "\n".join(block), encoding="utf-8")
        changed+=1
        logger.write(action="faq_embed", result="ok", idem=txt.stem, intent=None, err_type=reason)
    logger.write(action="faq_embed_done", result="ok", moved=changed)
    print(f"[OK] FAQ embedded -> {changed} files (force={force} min_score={min_score})")

if __name__=="__main__":
    main()
