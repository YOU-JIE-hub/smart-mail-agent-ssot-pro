#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, re
from pathlib import Path
ROOT=Path("/home/youjie/projects/smart-mail-agent_ssot").resolve()
BASE=ROOT/"reports_auto/e2e_mail"
def run_dirs():
  if not BASE.exists(): return []
  xs=[p for p in BASE.iterdir() if p.is_dir() and re.match(r"^\d{8}T\d{6}$", p.name)]
  xs.sort(key=lambda p: p.stat().st_mtime, reverse=True); return xs
def main():
  rs=run_dirs()
  if not rs:
    print("[FATAL] no timestamped e2e run dir"); sys.exit(2)
  run=rs[0]
  issues=[]; counts={}
  subs=["rpa_out/quotes","rpa_out/tickets","rpa_out/faq_replies","rpa_out/diffs","rpa_out/email_outbox"]
  for sub in subs:
    p=run/sub
    if not p.exists(): issues.append(f"missing_dir:{p}"); counts[sub]=0; continue
    n=sum(1 for _ in p.iterdir() if _.is_file()); counts[sub]=n
    if n==0: issues.append(f"empty:{p}")
  qp=run/"rpa_out/quotes"
  if qp.exists():
    for f in qp.glob("*.html"):
      s=f.read_text("utf-8", errors="ignore")
      if "</html>" not in s.lower(): issues.append(f"broken_html:{f}")
  print(f"[RUN] {run}"); print("[COUNTS]", counts)
  print("[OK] RPA outputs valid" if not issues else "[ISSUE] "+";".join(issues))
if __name__=="__main__":
  main()
