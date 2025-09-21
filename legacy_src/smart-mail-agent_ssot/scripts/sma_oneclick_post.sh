#!/usr/bin/env bash
# 一鍵後處理：E2E(若可) → 回填 cases → 重路由 → 產物 → 驗證
# 所有錯誤落檔：reports_auto/errors/ONECLICK_POST_<ts>/error.log
set -Eeuo pipefail

TS="$(date +%Y%m%dT%H%M%S)"
ROOT="/home/youjie/projects/smart-mail-agent_ssot"
ERRDIR="$ROOT/reports_auto/errors/ONECLICK_POST_${TS}"
LOG="$ERRDIR/log.txt"
mkdir -p "$ERRDIR" "reports_auto/logs" "reports_auto/status" "reports_auto/eval" "configs" "src/smart_mail_agent/routing" "scripts"

log()   { printf '%s\n' "$*" | tee -a "$LOG" >&2; }
fatal() { printf '[FATAL] %s\n' "$*" | tee -a "$LOG" >&2; exit 2; }
trap 'echo "[ERR] line=$LINENO" | tee -a "$LOG" >&2' ERR

cd "$ROOT"
export PYTHONNOUSERSITE=1
export PYTHONPATH=".:src:scripts:.sma_tools:${PYTHONPATH:-}"
[ -f ".venv/bin/activate" ] && . .venv/bin/activate || true

# 1) 確保規則模組存在（若已存在不影響）
mkdir -p src/smart_mail_agent/routing configs
[ -f src/smart_mail_agent/__init__.py ] || echo "# -*- coding: utf-8 -*-" > src/smart_mail_agent/__init__.py
[ -f src/smart_mail_agent/routing/__init__.py ] || echo "# -*- coding: utf-8 -*-" > src/smart_mail_agent/routing/__init__.py
cat > src/smart_mail_agent/routing/intent_rules.py <<'PY'
# -*- coding: utf-8 -*-
import re, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
CFG  = ROOT / "configs" / "intent_rules.yml"
_DEFAULT = {
  "priority": ["投訴","報價","技術支援","規則詢問","資料異動","其他"],
  "patterns": {
    "投訴": r"(投訴|客訴|申訴|抱怨|不滿|退款|退費|賠償|complain|refund|chargeback|延遲|慢|退單|毀損|缺件|少寄|寄錯|沒收到|沒出貨|無回覆|拖延|體驗差|服務差|品質差)",
    "報價": r"(報價|試算|報價單|折扣|PO|採購|合約價|quote|pricing|estimate|quotation|SOW)",
    "技術支援": r"(錯誤|異常|無法|崩潰|連線|壞掉|502|500|bug|error|failure|stacktrace)",
    "規則詢問": r"(SLA|條款|合約|規範|政策|policy|流程|SOP|FAQ)",
    "資料異動": r"(更改|變更|修改|更新|異動|地址|電話|email|e-mail|帳號|個資|profile|變動)",
    "其他": r".*"
  }
}
def _load_yaml_or_json_text(txt: str):
  try:
    import yaml
    return yaml.safe_load(txt)
  except Exception:
    try:
      return json.loads(txt)
    except Exception:
      return None
def load_rules(cfg_path=CFG):
  obj = None
  if cfg_path.exists():
    try:
      obj = _load_yaml_or_json_text(cfg_path.read_text(encoding="utf-8"))
    except Exception:
      obj = None
  if not obj: obj = _DEFAULT
  prio = obj.get("priority", _DEFAULT["priority"])
  pats = {k: re.compile(v, re.I) for k, v in obj.get("patterns", _DEFAULT["patterns"]).items()}
  return prio, pats
PY
[ -f configs/intent_rules.yml ] || cat > configs/intent_rules.yml <<'YAML'
priority: [投訴, 報價, 技術支援, 規則詢問, 資料異動, 其他]
patterns:
  投訴: "(投訴|客訴|申訴|抱怨|不滿|退款|退費|賠償|complain|refund|chargeback|延遲|慢|退單|毀損|缺件|少寄|寄錯|沒收到|沒出貨|無回覆|拖延|體驗差|服務差|品質差)"
  報價: "(報價|試算|報價單|折扣|PO|採購|合約價|quote|pricing|estimate|quotation|SOW)"
  技術支援: "(錯誤|異常|無法|崩潰|連線|壞掉|502|500|bug|error|failure|stacktrace)"
  規則詢問: "(SLA|條款|合約|規範|政策|policy|流程|SOP|FAQ)"
  資料異動: "(更改|變更|修改|更新|異動|地址|電話|email|e-mail|帳號|個資|profile|變動)"
  其他: ".*"
YAML

# 2) 載入共用函式（若已存在則沿用）
cat > scripts/_lib_text_fallback.py <<'PY'
# -*- coding: utf-8 -*-
def pick_text(rec: dict) -> str:
  t = rec.get("text")
  if t and t.strip(): return t
  return (rec.get("subject","") + "\n" + rec.get("body","")).strip()
PY

# 3) 確保四支腳本存在（如先前已建立會被覆蓋成最新）
cat > scripts/sma_reroute_last_run_intent.py <<'PY'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os, json, re, traceback, time
from pathlib import Path
from collections import Counter
TS = time.strftime("%Y%m%dT%H%M%S")
ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot")
ERRDIR = ROOT / f"reports_auto/errors/REROUTE_CRASH_{TS}"
ERRDIR.mkdir(parents=True, exist_ok=True)
def log_fatal(msg, exc=None):
  (ERRDIR/"error.log").write_text(f"[TIME] {TS}\n[MSG] {msg}\n[EXC]\n{traceback.format_exc() if exc else ''}", encoding="utf-8")
  print(f"[FATAL] {msg}"); sys.exit(2)
def list_e2e_dirs():
  base = ROOT / "reports_auto/e2e_mail"
  if not base.exists(): return []
  ds = [p for p in base.iterdir() if p.is_dir()]
  ds.sort(key=lambda p: p.stat().st_mtime, reverse=True); return ds
def is_run_dir(p: Path) -> bool:
  return bool(re.match(r"^\d{8}T\d{6}$", p.name)) and (p/"cases.jsonl").exists()
def load_intent_model():
  import joblib, pickle
  model_p = ROOT / "artifacts" / "intent_pro_cal.pkl"
  try: return joblib.load(model_p)
  except Exception:
    with open(model_p, "rb") as f: return pickle.load(f)
def infer_intent(clf, texts):
  if hasattr(clf,"predict_proba"):
    probs = clf.predict_proba(texts); labels = list(getattr(clf,"classes_",[]))
    top_idx = probs.argmax(1)
    return [labels[i] for i in top_idx], [float(probs[i,idx]) for i,idx in enumerate(top_idx)]
  preds = clf.predict(texts); return list(preds), [1.0]*len(preds)
def main(argv):
  import argparse
  from smart_mail_agent.routing.intent_rules import load_rules
  from scripts._lib_text_fallback import pick_text
  ap = argparse.ArgumentParser()
  ap.add_argument("--list", action="store_true")
  ap.add_argument("--run-dir", default="")
  args = ap.parse_args(argv)
  if args.list:
    for p in list_e2e_dirs():
      status = "cases.jsonl" if (p/"cases.jsonl").exists() else "-"
      print(p.as_posix(), "|", status)
    return 0
  # 先用參數指定；否則選最新且有 cases.jsonl 的資料夾（允許空，實際檢查在下方）
  run = None
  if args.run_dir:
    run = ROOT / args.run_dir if not args.run_dir.startswith("/") else Path(args.run_dir)
    if not run.exists(): log_fatal(f"specified run-dir not found: {run}")
    if not (run/"cases.jsonl").exists(): log_fatal(f"cases.jsonl not found under specified run-dir: {run}")
  else:
    for d in list_e2e_dirs():
      if is_run_dir(d): run = d; break
    if run is None: log_fatal("no e2e run with cases.jsonl found")
  lines = [ln for ln in (run/"cases.jsonl").read_text("utf-8", errors="ignore").splitlines() if ln.strip()]
  if not lines: log_fatal(f"cases.jsonl is empty: {run}")
  th_path = ROOT/"reports_auto/intent_thresholds.json"
  th = json.loads(th_path.read_text(encoding="utf-8")) if th_path.exists() else {"其他":0.40,"報價":0.30,"技術支援":0.30,"投訴":0.30,"規則詢問":0.30,"資料異動":0.30}
  PRIORITY, RX = load_rules()
  cases = [json.loads(x) for x in lines]
  texts = [pick_text(r) for r in cases]
  clf = load_intent_model()
  top_lbl, top_conf = infer_intent(clf, texts)
  def apply_threshold_and_rules(lbl, conf, text):
    thr = th.get(lbl, th.get("其他",0.40))
    routed = lbl if conf >= thr else "其他"
    if routed == "其他":
      hits = [k for k, rx in RX.items() if rx.search(text or "")]
      for k in PRIORITY:
        if k in hits: return k, f"rule:{k}"
    return routed, None
  out_nd = run/"intent_reroute_suggestion.ndjson"
  out_csv= run/"intent_reroute_audit.csv"
  out_md = run/"intent_reroute_summary.md"
  orig=[]; final=[]
  with open(out_nd,"w",encoding="utf-8") as fnd, open(out_csv,"w",encoding="utf-8") as fcsv:
    fcsv.write("case_id,orig_intent,orig_conf,final_intent,reason\n")
    for r,lbl,conf,txt in zip(cases, top_lbl, top_conf, texts):
      new_lbl, reason = apply_threshold_and_rules(lbl, conf, txt)
      rec = {"case_id": r.get("case_id") or r.get("id"), "orig_intent": lbl, "orig_conf": conf, "final_intent": new_lbl, "reason": reason}
      fnd.write(json.dumps(rec, ensure_ascii=False)+"\n")
      fcsv.write(f"{rec['case_id']},{lbl},{conf:.3f},{new_lbl},{reason or ''}\n")
      orig.append(lbl); final.append(new_lbl)
  from collections import Counter
  c1=Counter(orig); c2=Counter(final); keys=sorted(set(list(c1.keys())+list(c2.keys())))
  lines=[f"- {k}: orig={c1.get(k,0)} -> final={c2.get(k,0)}" for k in keys]
  out_md.write_text("# Intent reroute summary\n"
                    f"- run_dir: {run.as_posix()}\n"
                    f"- thresholds: {json.dumps(th, ensure_ascii=False)}\n\n"
                    "## counts (orig -> final)\n"+"\n".join(lines)+"\n",
                    encoding="utf-8")
  print("[OK] write", out_nd.as_posix())
  print("[OK] write", out_csv.as_posix())
  print("[OK] write", out_md.as_posix())
  return 0
if __name__=="__main__":
  try: sys.exit(main(sys.argv[1:]))
  except SystemExit: raise
  except Exception as e: log_fatal("reroute failed", e)
PY
chmod +x scripts/sma_reroute_last_run_intent.py

cat > scripts/sma_patch_cases_from_db.py <<'PY'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, sys, json, time, sqlite3, traceback
from pathlib import Path
from collections import defaultdict
TS = time.strftime("%Y%m%dT%H%M%S")
ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot").resolve()
ERRDIR = ROOT / f"reports_auto/errors/PATCH_CASES_{TS}"
ERRDIR.mkdir(parents=True, exist_ok=True)
def log_error(msg, exc=False):
  (ERRDIR/"error.log").write_text(f"[TIME] {TS}\n[MSG] {msg}\n"+(traceback.format_exc() if exc else ""), encoding="utf-8")
def list_runs():
  base = ROOT/"reports_auto/e2e_mail"
  if not base.exists(): return []
  xs=[p for p in base.iterdir() if p.is_dir() and re.match(r"^\d{8}T\d{6}$", p.name)]
  xs.sort(key=lambda p: p.stat().st_mtime, reverse=True); return xs
def pick_latest_run():
  rs = list_runs(); return rs[0] if rs else None
def nonblank_lines(p: Path) -> int:
  if not p.exists(): return 0
  return sum(1 for ln in p.read_text("utf-8", errors="ignore").splitlines() if ln.strip())
def table_exists(cur, name: str) -> bool:
  cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (name,))
  return cur.fetchone() is not None
def get_columns(cur, table: str):
  cur.execute(f"PRAGMA table_info({table});"); return [r[1] for r in cur.fetchall()]
def main(argv):
  import argparse
  ap=argparse.ArgumentParser()
  ap.add_argument("--run-dir", default="")
  ap.add_argument("--force", action="store_true")
  args=ap.parse_args(argv)
  run = Path(args.run_dir)
  if not args.run_dir:
    run = pick_latest_run()
    if run is None: print("[FATAL] no e2e run dir"); log_error("no e2e run dir"); return 2
  elif not run.is_absolute():
    run = ROOT / args.run_dir
  if not run.exists(): print(f"[FATAL] run not found: {run}"); log_error(f"run not found: {run}"); return 2
  out_p = run/"cases.jsonl"
  if nonblank_lines(out_p)>0 and not args.force:
    print(f"[SKIP] cases.jsonl already non-empty: {out_p}"); return 0
  dbp = ROOT/"db/sma.sqlite"
  if not dbp.exists(): print(f"[FATAL] DB not found: {dbp}"); log_error(f"DB not found: {dbp}"); return 2
  con=sqlite3.connect(dbp.as_posix()); cur=con.cursor()
  def has(t): return table_exists(cur,t)
  has_intent=has("intent_preds"); has_kie=has("kie_spans"); has_cases=has("cases") or has("mail_cases")
  if not has_intent and not has_kie and not has_cases:
    print("[FATAL] no usable tables in DB"); log_error("no usable tables in DB"); return 2
  intents={}
  if has_intent:
    cols=get_columns(cur,"intent_preds")
    case_col="case_id" if "case_id" in cols else ("id" if "id" in cols else None)
    label_col=None
    for c in ["label","pred","pred_label","intent","pred_intent"]:
      if c in cols: label_col=c; break
    conf_col=None
    for c in ["conf","confidence","intent_conf","score","prob","proba"]:
      if c in cols: conf_col=c; break
    if case_col and label_col:
      cur.execute(f"SELECT {case_col},{label_col}"+(f",{conf_col}" if conf_col else "")+" FROM intent_preds;")
      for row in cur.fetchall():
        cid=row[0]; lbl=row[1]; conf=float(row[2]) if conf_col and row[2] is not None else None
        intents[cid]={"intent":lbl,"intent_conf":conf}
    else:
      print("[WARN] intent_preds missing expected columns; skip intents")
  from collections import defaultdict
  spans_map=defaultdict(list)
  if has_kie:
    cols=get_columns(cur,"kie_spans")
    case_col="case_id" if "case_id" in cols else ("id" if "id" in cols else None)
    key_col="key" if "key" in cols else ("label" if "label" in cols else None)
    val_col="value" if "value" in cols else None
    s_col="start" if "start" in cols else None
    e_col="end" if "end" in cols else None
    if case_col and key_col and val_col:
      cur.execute(f"SELECT {case_col},{key_col},{val_col}"+(f",{s_col}" if s_col else ",NULL")+(f",{e_col}" if e_col else ",NULL")+" FROM kie_spans;")
      for cid,lab,val,s,e in cur.fetchall():
        spans_map[cid].append({"label":lab,"start":s,"end":e,"value":val})
    else:
      print("[WARN] kie_spans missing expected columns; skip spans")
  subject_map={}; body_map={}
  if has_cases:
    tname="cases" if has("cases") else "mail_cases"
    cols=get_columns(cur,tname)
    case_col="case_id" if "case_id" in cols else ("id" if "id" in cols else None)
    subj_col="subject" if "subject" in cols else None
    body_col="body" if "body" in cols else None
    if case_col and (subj_col or body_col):
      cur.execute(f"SELECT {case_col},{subj_col or 'NULL'},{body_col or 'NULL'} FROM {tname};")
      for cid,sj,bd in cur.fetchall():
        if sj: subject_map[cid]=sj
        if bd: body_map[cid]=bd
  cids=set(intents.keys())|set(spans_map.keys())|set(subject_map.keys())|set(body_map.keys())
  created=0
  with open(out_p,"w",encoding="utf-8") as f:
    for cid in sorted(cids):
      rec={"case_id":cid}
      if cid in subject_map: rec["subject"]=subject_map[cid]
      if cid in body_map:    rec["body"]=body_map[cid]
      if cid in intents:     rec.update(intents[cid])
      if cid in spans_map:   rec.setdefault("fields",{})["spans"]=spans_map[cid]
      f.write(json.dumps(rec,ensure_ascii=False)+"\n"); created+=1
  print(f"[OK] write {out_p}  lines={created}")
  if created==0:
    print("[WARN] no lines created; check DB tables/columns"); log_error("no lines created from DB")
  return 0
if __name__=="__main__":
  try: sys.exit(main(sys.argv[1:]))
  except SystemExit: raise
  except Exception:
    log_error("fatal", exc=True); print("[FATAL] patch cases failed")
PY
chmod +x scripts/sma_patch_cases_from_db.py

cat > scripts/sma_make_rpa_placeholders.py <<'PY'
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
PY
chmod +x scripts/sma_make_rpa_placeholders.py

cat > scripts/validate_rpa_outputs.py <<'PY'
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
PY
chmod +x scripts/validate_rpa_outputs.py

# 4) 嘗試 E2E（若可）
if [ -f "sma_oneclick_all.sh" ]; then
  log "[INFO] run sma_oneclick_all.sh"; bash sma_oneclick_all.sh || true
elif [ -f "scripts/sma_e2e_mail.py" ]; then
  log "[INFO] run scripts/sma_e2e_mail.py data/demo_eml"; python scripts/sma_e2e_mail.py data/demo_eml || true
else
  log "[WARN] 無 E2E 腳本，略過執行"
fi

# 5) 先回填，再 reroute，再產出與驗證（修正你剛剛的順序）
latest="$(ls -1dt reports_auto/e2e_mail/* 2>/dev/null | head -n1 || true)"
log "[INFO] latest run dir = ${latest:-<none>}"

if [ -n "${latest:-}" ]; then
  log "[INFO] patch cases.jsonl from DB on latest run"
  python scripts/sma_patch_cases_from_db.py --run-dir "$latest" || true

  log "[INFO] reroute intent (threshold+rules) on the same run"
  python scripts/sma_reroute_last_run_intent.py --run-dir "$latest" || true

  log "[INFO] make RPA placeholders on the same run"
  python scripts/sma_make_rpa_placeholders.py --run-dir "$latest" || true
else
  log "[WARN] 無可用 run 目錄，跳過 patch/reroute/placeholder"
fi

log "[INFO] validate RPA outputs"
python scripts/validate_rpa_outputs.py || true

# 6) 摘要
latest="$(ls -1dt reports_auto/e2e_mail/* 2>/dev/null | head -n1 || true)"
if [ -n "$latest" ] && [ -f "$latest/RPA_PLACEHOLDER_SUMMARY.md" ]; then
  echo "# ONECLICK POST SUMMARY" | tee -a "$LOG"
  echo "run_dir: $latest" | tee -a "$LOG"
  sed -n '1,160p' "$latest/RPA_PLACEHOLDER_SUMMARY.md" | tee -a "$LOG"
else
  log "[WARN] 找不到 RPA_PLACEHOLDER_SUMMARY.md"
fi

log "[DONE] post pipeline finished"
