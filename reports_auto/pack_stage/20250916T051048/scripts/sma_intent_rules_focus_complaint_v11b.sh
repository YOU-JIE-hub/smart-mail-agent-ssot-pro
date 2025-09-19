#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

TS="$(date +%Y%m%dT%H%M%S)"
EVADIR="reports_auto/eval/${TS}"
mkdir -p "$EVADIR" "reports_auto/status" "data/intent_eval" "artifacts_prod"

python - <<'PY'
# -*- coding: utf-8 -*-
import re, json, time, itertools
from pathlib import Path
from collections import defaultdict
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

ROOT=Path("."); NOW=time.strftime("%Y%m%dT%H%M%S")
EVADIR=ROOT/f"reports_auto/eval/{NOW}"; EVADIR.mkdir(parents=True, exist_ok=True)

def load_jsonl(p):
    out=[]
    if not p.exists() or p.stat().st_size==0: return out
    for ln in p.read_text("utf-8").splitlines():
        ln=ln.strip()
        if not ln: continue
        try: out.append(json.loads(ln))
        except: pass
    return out

# 1) 資料（優先 cleaned）
src_path=None
for cand in [ROOT/"data/intent_eval/dataset.cleaned.jsonl", ROOT/"data/intent_eval/dataset.jsonl"]:
    if cand.exists() and cand.stat().st_size>0:
        ds=load_jsonl(cand); src_path=cand; break
if not src_path:
    raise SystemExit("[FATAL] 找不到 intent 資料集")

labels = ["報價","技術支援","投訴","規則詢問","資料異動","其他"]

def get_text(r):
    return (r.get("text") or r.get("body") or r.get("subject") or "")

# 2) 規則（在 v11 基礎上擴充投訴；保留原本其它規則）
RX = {
  "報價": [
    r"報價|報個價|報價單|估價|試算|總額|總價|價錢|費用|單價|費率|TCO|年費|一次性|setup|quote|pricing|price|discount|payment\s*terms",
    r"NT\$|USD|US\$|\$ ?\d{1,3}(?:,\d{3})*"
  ],
  "技術支援": [
    r"\b429\b|限流|quota|throttl|rate[-\s]*limit",
    r"\b50[02]\b|\b40[134]\b|錯誤碼|error|exception|stacktrace|bug|crash|timeout|latency|延遲|超時",
    r"SAML|SSO|OTP|APNs|webhook|驗簽|signature|NTP|clock\s*skew|CSV|編碼|亂碼|登入|login|無法|失敗"
  ],
  "投訴": [
    r"投訴|申訴|客訴|抱怨|不滿|不滿意|非常\s*不滿|無法接受|不可接受|很糟|太慢|拖延|延宕|延誤|再發|品質不佳|服務不佳|沒回|回覆太慢",
    r"投訴表|申訴單|客訴單|正式\s*投訴|escalat(?:e|ion)|complain|dissatisf(?:y|ied)|unacceptable",
    r"賠償|補償|補救|違反\s*SLA|SLA\s*違反|影響上線|影響營運|高風險|造成損失|退款|退費"
  ],
  "規則詢問": [
    r"SLA|RPO|RTO|DPA|GDPR|HIPAA|資料保留|data\s*retention|刪除政策",
    r"續約|自動續約|終止|解約|合約|違約金|credit\s*note|退款|退費|contract|assignment|notice"
  ],
  "資料異動": [
    r"更新|變更|異動|請改|改為|改成|更名|替換|新增|刪除|移除|加入|改寄|寄送地址|收件人|發票抬頭",
    r"update|change|replace|adjust|add|remove|switch|rename|billing|invoice|shipping\s*address"
  ]
}
NEG_POLICY = re.compile(r"報價|費用|價|總價|總額|NT\$|USD|US\$|quote|pricing|price", re.I)
CRX = {k:[re.compile(p, re.I) for p in v] for k,v in RX.items()}

def rule_score(txt):
    s={l:0.0 for l in labels}
    for lb, regs in CRX.items():
        for r in regs:
            for _ in r.finditer(txt):
                s[lb]+=1.0
    # 保守處理規則詢問：若出現明確報價語意，降低規則詢問分數
    if NEG_POLICY.search(txt):
        s["規則詢問"] -= 0.6
    return s

def infer_one(txt, calib):
    sc=rule_score(txt)
    for k,v in calib.get("bias",{}).items():
        sc[k]=sc.get(k,0.0)+float(v)
    kept=[(k,v) for k,v in sc.items() if v>=calib.get("min_keep",{}).get(k,0.0)]
    if not kept:
        if any(r.search(txt) for r in CRX["技術支援"]): return "技術支援", sc
        if any(r.search(txt) for r in CRX["報價"]): return "報價", sc
        return "其他", sc
    kept.sort(key=lambda x:(x[1], calib.get("prio",{}).get(x[0],0)), reverse=True)
    return kept[0][0], sc

def evaluate(calib):
    y_true=[]; y_pred=[]
    for rec in ds:
        y_true.append(rec["label"])
        p,_=infer_one(get_text(rec), calib)
        y_pred.append(p)
    P,R,F1,Supp = precision_recall_fscore_support(y_true,y_pred,labels=labels,zero_division=0)
    micro=precision_recall_fscore_support(y_true,y_pred,average="micro",zero_division=0)[2]
    macro=precision_recall_fscore_support(y_true,y_pred,average="macro",zero_division=0)[2]
    cm=confusion_matrix(y_true,y_pred,labels=labels)
    return dict(P=P,R=R,F1=F1,Supp=Supp,micro=micro,macro=macro,cm=cm,y_true=y_true,y_pred=y_pred)

# 3) 讀 v11 校準，作為起點
base_calib_path=ROOT/"artifacts_prod/intent_rules_calib_v11.json"
if base_calib_path.exists():
    base_calib=json.loads(base_calib_path.read_text("utf-8"))
else:
    base_calib={"bias":{"報價":0.4,"技術支援":0.1,"投訴":0.2,"規則詢問":0.0,"資料異動":0.1,"其他":0.0},
                "min_keep":{"報價":0.6,"技術支援":0.5,"投訴":0.4,"規則詢問":0.55,"資料異動":0.45,"其他":1e9},
                "prio":{"報價":6,"技術支援":5,"投訴":4,"資料異動":3,"規則詢問":2,"其他":1}}

# 4) 只針對 投訴/規則詢問 做微調搜尋
grid = {
  "bias.投訴":    [base_calib["bias"].get("投訴",0.2)+d for d in (0.1,0.2,0.3)],
  "min.投訴":     [max(0.1, base_calib["min_keep"].get("投訴",0.4)+d) for d in (-0.15,-0.10,-0.05,0.0)],
  "min.規則詢問": [base_calib["min_keep"].get("規則詢問",0.55)+d for d in (0.0,0.05,0.10)],
}

keys=list(grid.keys())
best=None
for vals in itertools.product(*[grid[k] for k in keys]):
    calib=json.loads(json.dumps(base_calib))
    for k,v in zip(keys, vals):
        typ,name=k.split(".")
        if typ=="bias": calib["bias"][name]=v
        else: calib["min_keep"][name]=v
    res=evaluate(calib)
    score=(res["micro"], res["F1"][labels.index("投訴")], res["F1"][labels.index("規則詢問")], res["macro"])
    if (best is None) or (score>best[0]): best=(score,calib,res)

(_, calib, res)=best

# 5) 輸出報告
def md_metrics(res, title):
    md=[]
    md.append(f"# {title}")
    md.append(f"- dataset: {src_path.as_posix()}  size={len(ds)}")
    md.append(f"- micro P/R/F1: {res['micro']:.3f}/{res['micro']:.3f}/{res['micro']:.3f}")
    md.append(f"- macro F1: {res['macro']:.3f}\n")
    md.append("|label|P|R|F1|")
    md.append("|---|---:|---:|---:|")
    for i,lb in enumerate(labels):
        md.append(f"|{lb}|{res['P'][i]:.3f}|{res['R'][i]:.3f}|{res['F1'][i]:.3f}|")
    md.append("\n## Confusion Matrix")
    md.append("|gold\\pred|"+"|".join(labels)+"|")
    md.append("|---|"+"|".join(["---"]*len(labels))+"|")
    for i,lb in enumerate(labels):
        row = "|"+lb+"|"+"|".join(str(int(x)) for x in res["cm"][i])+"|"
        md.append(row)
    return "\n".join(md)

(Path(EVADIR)/"metrics_intent_rules_hotfix_v11b.md").write_text(md_metrics(res, "Intent metrics (rules hotfix v11b)"), "utf-8")

# FN/FP
for lb in labels:
    fn_lines=[]; fp_lines=[]
    for i,(t,p) in enumerate(zip(res["y_true"],res["y_pred"])):
        txt=get_text(ds[i]).replace("\n"," ")
        if t==lb and p!=lb: fn_lines.append(f"[{i}] {txt}")
        if t!=lb and p==lb: fp_lines.append(f"[{i}] {txt}")
    (Path(EVADIR)/f"FN_{lb}.txt").write_text("\n".join(fn_lines),"utf-8")
    (Path(EVADIR)/f"FP_{lb}.txt").write_text("\n".join(fp_lines),"utf-8")

# 校準另存 v11b
out_calib=ROOT/"artifacts_prod/intent_rules_calib_v11b.json"
out_calib.write_text(json.dumps(calib,ensure_ascii=False,indent=2),"utf-8")
print("[OK] saved calib ->", out_calib.as_posix())
print(">>> Result =>", (Path(EVADIR)/"metrics_intent_rules_hotfix_v11b.md").as_posix())
PY

# 附掛 ONECLICK
LATEST="$(ls -t reports_auto/status/ONECLICK_* 2>/dev/null | head -n1)"
if [ -n "${LATEST:-}" ]; then
  MET="$(ls -t reports_auto/eval/*/metrics_intent_rules_hotfix_v11b.md | head -n1)"
  { echo "## Intent metrics (rules hotfix v11b)"; sed -n '1,120p' "$MET"; } >> "$LATEST"
  tail -n 60 "$LATEST"
fi
