#!/usr/bin/env bash
set -euo pipefail
cd /home/youjie/projects/smart-mail-agent_ssot
[ -f .venv/bin/activate ] && . .venv/bin/activate || true
export PYTHONNOUSERSITE=1

# 1) 主流程（你已經有 v11）
bash scripts/sma_oneclick_stage_pick_eval_v11.sh || true

# 2) 立刻補上 Intent(門檻+規則) 指標（就是你剛剛跑成功的 hotfix）
if [ ! -f scripts/sma_hotfix_intent_rules_metrics.sh ]; then
  cat > scripts/sma_hotfix_intent_rules_metrics.sh <<'PYX'
#!/usr/bin/env bash
set -euo pipefail
python - <<'PY'
import json, re, sys, types, pickle, math, time
from pathlib import Path
root=Path(".")
ds_p = root/"data/intent_eval/dataset.jsonl"
if not ds_p.exists() or ds_p.stat().st_size==0:
    print("[SKIP] intent_eval/dataset.jsonl is empty"); raise SystemExit(0)
ds=[json.loads(x) for x in ds_p.read_text("utf-8").splitlines() if x.strip()]
texts=[r.get("text") or r.get("body") or r.get("subject") or "" for r in ds]
gold=[r.get("intent") or r.get("label") or "其他" for r in ds]
th_p = root/"reports_auto/intent_thresholds.json"
th = json.loads(th_p.read_text("utf-8")) if th_p.exists() else {"其他":0.4,"報價":0.3,"技術支援":0.3,"投訴":0.25,"規則詢問":0.3,"資料異動":0.3}
rx_file = root/"configs/intent_rules_compiled.json"
if rx_file.exists():
    J=json.loads(rx_file.read_text("utf-8"))
    pri=J.get("priority") or ["投訴","報價","技術支援","規則詢問","資料異動"]
    RX={k:re.compile(v,re.I) for k,v in (J.get("patterns") or {}).items()}
else:
    pri=["投訴","報價","技術支援","規則詢問","資料異動"]
    pat={
     "投訴": r"(投訴|客訴|申訴|抱怨|不滿|退款|退費|賠償|complain|refund|chargeback|延遲|慢|退單|毀損|缺件|少寄|寄錯|沒收到|沒出貨|無回覆|拖延|體驗差|服務差|品質差)",
     "報價": r"(報價|試算|報價單|折扣|PO|採購|合約價|quote|pricing|estimate|quotation|SOW)",
     "技術支援": r"(錯誤|異常|無法|崩潰|連線|壞掉|502|500|bug|error|failure|stacktrace)",
     "規則詢問": r"(SLA|條款|合約|規範|政策|policy|流程|SOP|FAQ)",
     "資料異動": r"(更改|變更|修改|更新|異動|地址|電話|email|e-mail|帳號|個資|profile|變動)"
    }
    RX={k:re.compile(v,re.I) for k,v in pat.items()}
def rule_pick(t:str):
    for lab in pri:
        r=RX.get(lab)
        if r and r.search(t or ""): return lab
    return None
# 讓舊 pickle 能載
from smart_mail_agent.ml.rules_feat import rules_feat as _rf
m = sys.modules.get("__main__") or types.ModuleType("__main__")
setattr(m,"rules_feat",_rf); sys.modules["__main__"]=m

model=None
for p in ["artifacts/intent_pro_cal.pkl","artifacts/intent_pipeline_fixed.pkl","artifacts/intent_clf.pkl"]:
    pp=Path(p)
    if not pp.exists(): continue
    try:
        try:
            import joblib; model=joblib.load(pp)
        except Exception:
            model=pickle.loads(pp.read_bytes())
        print("[OK] loaded intent model:", p); break
    except Exception as e:
        print("[WARN] load fail", p, "->", e)

def softmax(a):
    if not a: return []
    import math
    m=max(a); ex=[math.exp(x-m) for x in a]; s=sum(ex) or 1.0
    return [e/s for e in ex]

def map2zh(lbl):
    mp={"biz_quote":"報價","quote":"報價","pricing":"報價","estimate":"報價","quotation":"報價",
        "tech_support":"技術支援","support":"技術支援","bug":"技術支援","issue":"技術支援","ticket":"技術支援",
        "complaint":"投訴","refund":"投訴","chargeback":"投訴","return":"投訴","claim":"投訴",
        "policy_qa":"規則詢問","faq":"規則詢問","policy":"規則詢問","terms":"規則詢問","sla":"規則詢問",
        "profile_update":"資料異動","account_update":"資料異動","change_request":"資料異動","update":"資料異動","profile":"資料異動",
        "other":"其他","misc":"其他","general":"其他"}
    s=str(lbl).strip()
    if s in {"報價","技術支援","投訴","規則詢問","資料異動","其他"}: return s
    return mp.get(s.lower(),"其他")

pred=[]
if model:
    classes=getattr(model,"classes_",None)
    for t in texts:
        try:
            if hasattr(model,"predict_proba"):
                pb=list(model.predict_proba([t])[0]); i=max(range(len(pb)), key=lambda k: pb[k])
                conf=float(pb[i]); lab=map2zh(classes[i] if classes is not None else i)
            elif hasattr(model,"decision_function"):
                sc=model.decision_function([t])[0]
                if hasattr(sc,"__len__"): pr=softmax(list(sc)); i=max(range(len(pr)), key=lambda k: pr[k]); conf=float(pr[i])
                else: conf=1/(1+math.exp(-float(sc))); i=0
                lab=map2zh(classes[i] if classes is not None else i)
            else:
                lab=map2zh(model.predict([t])[0]); conf=0.5
        except Exception:
            lab=None; conf=0.0
        thr=th.get(lab, th.get("其他",0.4))
        routed = (rule_pick(t) or "其他") if (lab is None or conf < thr) else (rule_pick(t) or lab)
        pred.append(routed)
else:
    pred=[rule_pick(t) or "其他" for t in texts]

labels=sorted(set(gold)|set(pred)|set(th.keys()))
cm={lab:{"tp":0,"fp":0,"fn":0} for lab in labels}
for g,p in zip(gold,pred):
    if p==g: cm[g]["tp"]+=1
    else: cm[p]["fp"]+=1; cm[g]["fn"]+=1

def prf(m):
    tp,fp,fn=m["tp"],m["fp"],m["fn"]
    P= tp/(tp+fp) if (tp+fp)>0 else 0.0
    R= tp/(tp+fn) if (tp+fn)>0 else 0.0
    F1= 2*P*R/(P+R) if (P+R)>0 else 0.0
    return P,R,F1

rows=[]; mf=0.0
for lab in labels:
    P,R,F1=prf(cm[lab]); rows.append((lab,P,R,F1,cm[lab]["tp"],cm[lab]["fp"],cm[lab]["fn"])); mf+=F1
mf=mf/len(labels) if labels else 0.0

# 落到最新 eval 目錄
eds=sorted([p for p in (root/"reports_auto/eval").glob("*") if p.is_dir()], key=lambda p:p.stat().st_mtime)
out = eds[-1] if eds else (root/"reports_auto/eval/INTENT_RULES_"+time.strftime("%Y%m%dT%H%M%S"))
out.mkdir(parents=True, exist_ok=True)
md=["# Intent metrics (threshold + rules)",
    f"- thresholds: {json.dumps(th,ensure_ascii=False)}",
    f"- macro_f1_after_threshold_and_rules: {mf:.3f}",
    "",
    "|label|P|R|F1|TP|FP|FN|",
    "|---|---:|---:|---:|---:|---:|---:|"]
for lab,Pv,Rv,F1,TP,FP,FN in rows:
    md.append(f"|{lab}|{Pv:.3f}|{Rv:.3f}|{F1:.3f}|{TP}|{FP}|{FN}|")
(out/"metrics_after_threshold_and_rules.md").write_text("\n".join(md),"utf-8")
print("[OK] wrote", out/"metrics_after_threshold_and_rules.md")

# 附到最新 ONECLICK v11/v10 摘要
sts=sorted((root/"reports_auto/status").glob("ONECLICK_v1*"), key=lambda p:p.stat().st_mtime)
if sts:
    with sts[-1].open("a",encoding="utf-8") as f:
        f.write("\n## Intent(threshold+rules) metrics (auto)\n")
        f.write("\n".join(md[:160]))
    print("[OK] appended metrics to", sts[-1])
PY
PYX
  chmod +x scripts/sma_hotfix_intent_rules_metrics.sh
fi

bash scripts/sma_hotfix_intent_rules_metrics.sh || true
echo "[DONE] one-click v11 + rules-metrics"
