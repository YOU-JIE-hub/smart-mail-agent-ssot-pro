#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, re, time, traceback
from pathlib import Path
TS=time.strftime("%Y%m%dT%H%M%S")
ROOT=Path("/home/youjie/projects/smart-mail-agent_ssot").resolve()
ERRDIR=ROOT/f"reports_auto/errors/RPA_PLACEHOLDER_{TS}"
ERRDIR.mkdir(parents=True, exist_ok=True)
def list_runs():
  base=ROOT/"reports_auto/e2e_mail"
  if not base.exists(): return []
  xs=[p for p in base.iterdir() if p.is_dir() and re.match(r"^\d{8}T\d{6}$", p.name)]
  xs.sort(key=lambda p: p.stat().st_mtime, reverse=True); return xs
def find_latest_nonempty():
  for p in list_runs():
    cj=p/"cases.jsonl"
    if cj.exists():
      try:
        lines=[ln for ln in cj.read_text("utf-8",errors="ignore").splitlines() if ln.strip()]
        if lines: return p
      except Exception: continue
  return None
def pick_text(rec: dict) -> str:
  t=rec.get("text")
  if t and t.strip(): return t
  return (rec.get("subject","")+"\n"+rec.get("body","")).strip()
def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("--run-dir", default="")
  args=ap.parse_args()
  run = Path(args.run_dir) if args.run_dir else find_latest_nonempty()
  if run and not run.is_absolute() and args.run_dir: run = ROOT/run
  if not run or not run.exists():
    (ERRDIR/"error.log").write_text("[FATAL] no non-empty e2e run dir found\n", encoding="utf-8")
    print("[FATAL] no non-empty e2e run dir found"); return 2
  cases_p=run/"cases.jsonl"
  if not cases_p.exists():
    (ERRDIR/"error.log").write_text(f"[FATAL] no cases.jsonl in {run}\n", encoding="utf-8")
    print("[FATAL] no cases.jsonl"); return 2
  raw_lines=cases_p.read_text("utf-8",errors="ignore").splitlines()
  nonblank=[ln for ln in raw_lines if ln.strip()]
  total=len(raw_lines); nb=len(nonblank)
  out_base=run/"rpa_out"
  for sub in ["quotes","tickets","faq_replies","diffs","email_outbox"]:
    (out_base/sub).mkdir(parents=True, exist_ok=True)
  stats={"run_dir":run.as_posix(),"cases_total_lines":total,"cases_nonblank_lines":nb,"json_ok":0,"json_error":0,"created":{"quotes":0,"tickets":0,"faq_replies":0,"diffs":0,"email_outbox":0}}
  for ln in nonblank:
    try:
      r=json.loads(ln); stats["json_ok"]+=1
    except Exception:
      stats["json_error"]+=1
      (ERRDIR/"error.log").write_text(f"[JSON_ERROR] {ln[:400]}\n", encoding="utf-8"); continue
    cid=r.get("case_id") or r.get("id") or f"noid-{TS}"
    text=pick_text(r)
    subj=r.get("subject") or "Re: your inquiry"
    sender=r.get("from") or "noreply@example.com"
    to=r.get("to") or "customer@example.com"
    (out_base/"quotes"/f"{cid}.html").write_text(
      "<!doctype html><html><head><meta charset='utf-8'><title>Quote</title></head>"
      "<body><h1>Preliminary Quote</h1>"
      f"<p>Case: {cid}</p><ul><li>amount: TBD</li><li>sla: TBD</li><li>env: TBD</li><li>valid_until: TBD</li></ul>"
      "</body></html>", encoding="utf-8"); stats["created"]["quotes"]+=1
    (out_base/"tickets"/f"{cid}.json").write_text(json.dumps({
      "ticket_id": cid, "title": subj[:120], "severity": "P3", "status": "open",
      "created_at": TS, "requester": to, "assignee": None,
      "tags": ["auto-generated","placeholder"], "description": (text or "")[:2000]
    }, ensure_ascii=False, indent=2), encoding="utf-8"); stats["created"]["tickets"]+=1
    (out_base/"faq_replies"/f"{cid}.md").write_text(
      f"# FAQ reply draft\n\n- case: {cid}\n- subject: {subj}\n\n參考答案：請見公司 FAQ 之 SLA/條款/流程章節。\n", encoding="utf-8"); stats["created"]["faq_replies"]+=1
    (out_base/"diffs"/f"{cid}.json").write_text(json.dumps({
      "case_id": cid, "diff": [{"field":"email","old": None,"new": to}], "status":"draft"
    }, ensure_ascii=False, indent=2), encoding="utf-8"); stats["created"]["diffs"]+=1
    (out_base/"email_outbox"/f"{cid}.eml").write_text(
      f"From: {sender}\r\nTo: {to}\r\nSubject: {subj}\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n您好，這是系統自動產生的回覆草稿，內容待業務/客服確認後寄出。\r\n", encoding="utf-8"); stats["created"]["email_outbox"]+=1
  (run/"RPA_PLACEHOLDER_SUMMARY.md").write_text(
    "# RPA placeholder summary\n"
    f"- run_dir: {stats['run_dir']}\n"
    f"- cases_total_lines: {stats['cases_total_lines']}\n"
    f"- cases_nonblank_lines: {stats['cases_nonblank_lines']}\n"
    f"- json_ok: {stats['json_ok']}\n"
    f"- json_error: {stats['json_error']}\n"
    f"- created: {json.dumps(stats['created'], ensure_ascii=False)}\n", encoding="utf-8")
  print("[OK] placeholders created under", (run/"rpa_out").as_posix())
  if sum(stats["created"].values())==0:
    print("[WARN] no files created; check cases.jsonl content or JSON errors in", ERRDIR.as_posix())
  return 0
if __name__=="__main__":
  try: raise SystemExit(main())
  except SystemExit: pass
  except Exception:
    (ERRDIR/"error.log").write_text(traceback.format_exc(), encoding="utf-8")
    print("[FATAL] placeholder generation failed")
