#!/usr/bin/env bash
set -Eeuo pipefail -o errtrace; umask 022
cd ~/projects/smart-mail-agent-ssot-pro || exit 2
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1 PYTHONPATH="src:${PYTHONPATH:-}"

TS="$(date +%Y%m%dT%H%M%S)"; ROOT="$PWD"
ACTROOT="$ROOT/reports_auto/actions"; mkdir -p "$ACTROOT"
ERRDIR="$ROOT/reports_auto/ERR/$TS"; LOGDIR="$ROOT/reports_auto/logs/$TS"; BUNDLEDIR="$ROOT/reports_auto/bundles"
mkdir -p "$ERRDIR" "$LOGDIR" "$BUNDLEDIR"

OUTROOT="$ACTROOT/actions_${TS}_batch6"; mkdir -p "$OUTROOT"; export OUTROOT

# 收斂
python - <<'PY' 1>>"$LOGDIR/actions_batch6.collect.out" 2>>"$ERRDIR/actions_batch6.collect.err"
import json, re, os
from pathlib import Path
OUTROOT=Path(os.getenv("OUTROOT"))
def as_id(s): return re.sub(r'[^A-Za-z0-9\u4e00-\u9fff._-]+','_', (s or "mail").strip())[:80] or "mail"
actions=[
  {"mail": as_id("demo_make_quote_pdf"), "intent":"報價","action":"make_quote_pdf",
   "fields":{"customer":"示例客戶","items":[{"name":"企業版授權","qty":20,"unit_price":1500},{"name":"導入","qty":1,"unit_price":30000}], "tax_rate":0.05}},
  {"mail": as_id("demo_create_ticket"), "intent":"技術支援","action":"create_ticket",
   "fields":{"severity":"major","component":"api","has_logs": True}},
  {"mail": as_id("demo_escalation_suggestion"), "intent":"投訴","action":"escalation_suggestion",
   "fields":{"sla":"24h","tone":"apology"}},
  {"mail": as_id("demo_faq_reply_draft"), "intent":"規則詢問","action":"faq_reply_draft",
   "fields":{"topic":"refund"}},
  {"mail": as_id("demo_crm_update"), "intent":"資料異動","action":"crm_update",
   "fields":{"name":"王小明","phone":"0912-345-678","email":"user@example.com","address":"台北市中正區XXX"}},
  {"mail": as_id("demo_human_handoff"), "intent":"其他","action":"human_handoff",
   "fields":{"summary":"一般詢問，請人工處理"}}
]
(OUTROOT/"_collected_actions.json").write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[OK] collected {len(actions)} ->", OUTROOT)
PY

# 執行（同 action_one 的處理流程）
python tools/action_one.sh >/dev/null 2>&1 || true  # 預熱 venv/相依
python - <<'PY' 1>>"$LOGDIR/actions_batch6.exec.out" 2>>"$ERRDIR/actions_batch6.exec.err"
import json, re, datetime, os, math
from pathlib import Path
OUTROOT=Path(os.getenv("OUTROOT"))
log=(OUTROOT/"actions_detail.log").open("a", encoding="utf-8")

def safe_name(s): s=str(s or "").strip(); s=re.sub(r'[^A-Za-z0-9\u4e00-\u9fff._-]+','_',s); return s[:80] or "mail"
def to_float(x,d=0.0):
    try:
        if x in (None,"","null","None"): return d
        if isinstance(x,(int,float)) and (not math.isnan(x) and not math.isinf(x)): return float(x)
        return float(str(x).replace(",","").strip())
    except Exception: return d
def to_int(x,d=0):
    try: return int(round(to_float(x,d)))
    except Exception: return d
def as_str(x):
    try: return str(x) if x is not None else ""
    except Exception: return ""
def mask_phone(s): return re.sub(r'(?:(?:\+?886\-?)?0?9\d{2})[\-\s]?\d{3}[\-\s]?\d{3}', lambda m: m.group(0)[:4]+"-***-***", as_str(s))
def mask_email(s):
    s=as_str(s); return re.sub(r'([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)(@[^,\s>]+)', lambda m: (m.group(1)+"***"+m.group(3)), s)
def rag_search(query:str,k:int=3):
    roots=[Path("policies"), Path("data/faq")]
    toks=set(re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", query or ""))
    hits=[]
    for r in roots:
        for p in r.rglob("*"):
            if p.suffix.lower() not in {".md",".txt"}: continue
            try:
                txt=p.read_text(encoding="utf-8")
            except Exception:
                try: txt=p.read_text(encoding="utf-8", errors="ignore")
                except Exception: continue
            sents=re.split(r"(?<=[。！？.!?])\s+", txt)
            score=sum(txt.count(t) for t in toks if len(t)>=2) or len(toks & set(re.findall(r"[A-Za-z0-9\u4e00-\u9fff]+", txt)))
            if score>0:
                top=[]
                for s in sents:
                    sc=sum(s.count(t) for t in toks if len(t)>=2)
                    if sc>0: top.append((sc,s.strip()))
                top=[s for _,s in sorted(top,key=lambda x:-x[0])[:2]]
                hits.append((score,p,top))
    hits=sorted(hits,key=lambda x:-x[0])[:k]
    return [{"file":str(p),"snippets":s} for _,p,s in hits]

try:
    actions=json.loads((OUTROOT/"_collected_actions.json").read_text(encoding="utf-8"))
except Exception as e:
    log.write(f"[FATAL] cannot read _collected_actions.json: {type(e).__name__}: {e}\n"); actions=[]

now=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"); records=[]
for it in actions:
    mail=safe_name(it.get("mail","unknown")); act=str(it.get("action","human_handoff")); fields=it.get("fields") or {}
    outdir=OUTROOT/mail; outdir.mkdir(parents=True, exist_ok=True)
    rec={"mail":mail,"action":act,"ok":True}; arts=[]
    try:
        if act=="make_quote_pdf":
            raw=fields.get("items") or [{"name":"企業版授權","qty":10,"unit_price":1000}]
            items=[]
            for r in raw if isinstance(raw,list) else [raw]:
                items.append({"name":str(r.get("name","項目")),"qty":int(round(float(str(r.get("qty",1)).replace(',','') or 0))),"unit_price":float(str(r.get("unit_price",0)).replace(',','') or 0.0)})
            tax_rate=float(str(fields.get("tax_rate",0.05)).replace(',','') or 0.05)
            subtotal=sum(i["qty"]*i["unit_price"] for i in items); tax=round(subtotal*tax_rate,2); total=subtotal+tax
            rows="".join([f"<tr><td>{i['name']}</td><td style='text-align:right'>{i['qty']}</td><td style='text-align:right'>{i['unit_price']:.2f}</td><td style='text-align:right'>{i['qty']*i['unit_price']:.2f}</td></tr>" for i in items])
            html=f"""<!doctype html><meta charset="utf-8"><style>body{{font-family:Arial; margin:24px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:8px}}</style>
<h2>報價單 QUOTATION</h2><p>客戶：{str(fields.get('customer','示例客戶'))} | 日期：{now}</p>
<table><thead><tr><th>項目</th><th>數量</th><th>單價</th><th>小計</th></tr></thead><tbody>{rows}</tbody>
<tfoot><tr><td colspan="3">小計</td><td style='text-align:right'>{subtotal:.2f}</td></tr><tr><td colspan="3">稅額({tax_rate*100:.0f}%)</td><td style='text-align:right'>{tax:.2f}</td></tr><tr><td colspan="3"><b>總額</b></td><td style='text-align:right'><b>{total:.2f}</b></td></tr></tfoot></table>"""
            (outdir/"quote.html").write_text(html,encoding="utf-8"); arts.append({"kind":"html","path":str(outdir/'quote.html')})
        elif act=="create_ticket":
            p=outdir/"ticket.json"; p.write_text(json.dumps({"title":"[技術支援] 自動建單","severity":str(fields.get("severity","minor")),"component":str(fields.get("component","api")),"has_logs":bool(fields.get("has_logs",False)),"created_at":now}, ensure_ascii=False, indent=2), encoding="utf-8"); arts.append({"kind":"json","path":str(p)})
        elif act=="escalation_suggestion":
            p=outdir/"escalation.md"; p.write_text("# 投訴升級建議\n\n- SLA：24h\n- 1) 致歉與確認\n- 2) 調查與回報節點\n- 3) 補償與關閉條件\n", encoding="utf-8"); arts.append({"kind":"md","path":str(p)})
        elif act=="faq_reply_draft":
            def rag_search_local(q): return rag_search(q,3)
            p=outdir/"reply.md"; topic=str(fields.get("topic","general")); refs=rag_search_local(topic or "refund 退貨 退款")
            body=[f"# 規則回覆草稿\n","- 這是自動草稿，可再由人工審閱修飾。\n",f"- 主題：{topic}\n"]
            if refs:
                body.append("\n## 參考資料（自動擷取）\n")
                for i,ref in enumerate(refs, start=1):
                    body.append(f"- {i}. {ref['file']}\n")
                    for s in ref["snippets"]: body.append(f"  > {s}\n")
            else:
                body.append("\n> 未找到本地政策/FAQ；請補足 `policies/*.md` 或 `data/faq/*.md`\n")
            p.write_text("".join(body),encoding="utf-8"); arts.append({"kind":"md","path":str(p)})
        elif act=="crm_update":
            p=outdir/"crm_update.json"; payload={}
            for k,v in (fields.items() if isinstance(fields, dict) else []):
                kl=str(k).lower()
                if kl in ("phone","tel","mobile","address"): payload[k]=re.sub(r'(?:(?:\+?886\-?)?0?9\d{2})[\-\s]?\d{3}[\-\s]?\d{3}', lambda m: m.group(0)[:4]+"-***-***", str(v))
                elif kl in ("email","mail"): payload[k]=re.sub(r'([A-Za-z0-9._%+-])([A-Za-z0-9._%+-]*)(@[^,\s>]+)', lambda m: (m.group(1)+"***"+m.group(3)), str(v))
                else: payload[k]=str(v) if v is not None else ""
            payload.setdefault("dry_run", True); payload["updated_at"]=now
            p.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); arts.append({"kind":"json","path":str(p)})
        else:
            p=outdir/"handoff.md"; p.write_text("# 人工轉派\n\n- 摘要：一般詢問（請人工接手）\n", encoding="utf-8"); arts.append({"kind":"md","path":str(p)})
    except Exception as e:
        records.append({"mail":mail,"action":act,"ok":False,"error":f"{type(e).__name__}: {e}","artifacts":arts})
    else:
        records.append({"mail":mail,"action":act,"ok":True,"artifacts":arts})

ok=sum(1 for r in records if r.get("ok"))
(OUTROOT/"actions_summary.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
(OUTROOT/"actions_summary.md").write_text("# Actions Summary\n\n- 總數：%d\n- OK：%d\n"%(len(records),ok),encoding="utf-8")
print("[OK] actions batch6 ->", OUTROOT, "OK:", ok, "TOTAL:", len(records))
PY

# latest 指向 + bundle
python - <<'PY'
from pathlib import Path; import shutil
root=Path("reports_auto/actions")
dirs=sorted([p for p in root.glob("actions_*") if p.is_dir()], key=lambda p:p.name, reverse=True)
if dirs:
    latest=root/"latest"
    try:
        if latest.exists() or latest.is_symlink(): latest.unlink()
        latest.symlink_to(dirs[0].name)
    except Exception:
        if latest.exists(): shutil.rmtree(latest, ignore_errors=True)
        import shutil as _sh; _sh.copytree(dirs[0], latest, dirs_exist_ok=True)
print("[OK] latest ->", dirs[0] if dirs else "NA")
PY
TS="$(date +%Y%m%dT%H%M%S)"; ZIP="reports_auto/bundles/actions_${TS}_batch6.zip"
zip -qr "$ZIP" "$OUTROOT" || true
( cd reports_auto/bundles && sha256sum "$(basename "$ZIP")" > "SHA256SUMS_${TS}_batch6" ) || true
echo "[OK] bundle -> $ZIP"
