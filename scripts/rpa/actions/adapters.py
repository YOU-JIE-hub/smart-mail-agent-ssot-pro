import json, pathlib, time, hashlib
from scripts.obs.audit import audit_action
OUTROOT=pathlib.Path("reports_auto/actions")
def _ts(): return time.strftime("%Y%m%dT%H%M%S")
def _idem(text): return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
def _mk(intent): d=OUTROOT/(_ts())/f"intent={intent}"; d.mkdir(parents=True, exist_ok=True); return d
def gen_quote(intent, text):
    d=_mk(intent); idem=_idem(text)
    obj={"intent":intent,"ts":_ts(),"items":[{"name":"Service","qty":1,"price":1000}],"currency":"TWD"}
    (d/f"quote_{idem}.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    # PDF 降級：若無 reportlab，寫 .txt
    try:
        from reportlab.pdfgen import canvas
        p=str(d/f"quote_{idem}.pdf"); c=canvas.Canvas(p); c.drawString(72, 720, "QUOTE TWD 1000"); c.save()
    except Exception:
        (d/f"quote_{idem}.txt").write_text("QUOTE: TWD 1000", encoding="utf-8")
    audit_action(intent,"gen_quote",obj,idem)
    return {"ok":True,"idem":idem}
def post_webhook(intent, text, url=None):
    d=_mk(intent); idem=_idem(text)
    rsp={"status":202,"sink":url or "mock://sink","echo":True}
    (d/f"webhook_{idem}.json").write_text(json.dumps(rsp,ensure_ascii=False,indent=2),encoding="utf-8")
    audit_action(intent,"post_webhook",rsp,idem)
    return {"ok":True}
def create_ticket(intent, text):
    d=_mk(intent); idem=_idem(text)
    obj={"title":"客訴單","desc":text[:200]}
    (d/f"ticket_{idem}.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    audit_action(intent,"create_ticket",obj,idem)
    return {"ok":True}
def draft_answer(intent, text):
    d=_mk(intent); idem=_idem(text)
    md=f"# 回覆草稿\n\n{text[:400]}\n"
    (d/f"answer_{idem}.md").write_text(md, encoding="utf-8")
    audit_action(intent,"draft_answer",{"path":str(d)},idem)
    return {"ok":True}
def crm_update(intent, text):
    d=_mk(intent); idem=_idem(text)
    obj={"event":"profile_update","fields":{"raw":text[:200]}}
    (d/f"crm_{idem}.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    audit_action(intent,"crm_update",obj,idem)
    return {"ok":True}
def create_issue(intent, text):
    d=_mk(intent); idem=_idem(text)
    md=f"# ISSUE\n\n{text[:400]}\n"
    (d/f"issue_{idem}.md").write_text(md, encoding="utf-8")
    audit_action(intent,"create_issue",{"path":str(d)},idem)
    return {"ok":True}
def handoff_human(intent, text):
    d=_mk(intent); idem=_idem(text)
    obj={"handoff":True,"note":"需要人工判斷","snippet":text[:200]}
    (d/f"handoff_{idem}.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
    audit_action(intent,"handoff_human",obj,idem)
    return {"ok":True}
# 融合 LLM / RAG
from scripts.llm.gateway import summarize
def llm_summarize(intent, text):
    d=_mk(intent); idem=_idem(text)
    out = summarize(intent, text, task="complaint_summary")
    (d/f"summary_{idem}.md").write_text(out, encoding="utf-8")
    audit_action(intent,"llm_summarize",{"len":len(text)},idem)
    return {"ok":True}
from scripts.rag.query import answer as rag_answer_func
def rag_answer(intent, text):
    d=_mk(intent); idem=_idem(text)
    # 使用 text 當作問句
    import io, sys
    buff=io.StringIO(); 
    # 捕捉標準輸出
    import contextlib
    with contextlib.redirect_stdout(buff):
        try: rag_answer_func(text)
        except SystemExit: pass
    out=buff.getvalue()
    (d/f"rag_{idem}.txt").write_text(out, encoding="utf-8")
    audit_action(intent,"rag_answer",{"len":len(text)},idem)
    return {"ok":True}
