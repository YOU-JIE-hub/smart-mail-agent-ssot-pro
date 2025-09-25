from scripts._lib_text_fallback import pick_text as __pick_text
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
將門檻路由 + 關鍵詞規則應用到最新 intent 評估結果，輸出：
reports_auto/eval/<INTENT_DIR>/metrics_after_threshold_and_rules.md
"""
import json, glob, os, re
from pathlib import Path

ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot")

# 取「最新且 dataset_size>1」的 intent 評估資料夾
cands=[]
for m in glob.glob(str(ROOT/"reports_auto/eval/*/metrics.json")):
    j=json.load(open(m,"r",encoding="utf-8"))
    if j.get("dataset_size",0)>1:
        cands.append(os.path.dirname(m))
cands.sort()
INTENT_DIR=cands[-1]

th = json.load(open(ROOT/"reports_auto/intent_thresholds.json","r",encoding="utf-8"))
ds = [json.loads(x) for x in open(ROOT/"data/intent_eval/dataset.jsonl","r",encoding="utf-8")]
pr = [json.loads(x) for x in open(os.path.join(INTENT_DIR,"eval_pred.jsonl"),"r",encoding="utf-8")]

# 規則詞庫（最小可行集，可再擴充）
# RX moved to shared module
from smart_mail_agent.routing.intent_rules import load_rules
PRIORITY, RX = load_rules()[0], load_rules()[1]
RX = RX  # keep name
    "投訴": re.compile(r"(投訴|客訴|申訴|抱怨|不滿|退款|退費|賠償|投訴單|complain|refund|chargeback|延遲|慢|退單|毀損|缺件|少寄|寄錯|沒收到|沒出貨|無回覆|拖延|體驗差|服務差|品質差)", re.I)|延遲|慢|退單|毀損|缺件|少寄|寄錯|沒收到|沒出貨|無回覆|拖延|體驗差|服務差|品質差", re.I),
    "報價": re.compile(r"(報價|試算|報價單|折扣|PO|採購|合約價|quote|pricing|estimate|quotation|SOW)", re.I),
    "技術支援": re.compile(r"(錯誤|異常|無法|崩潰|連線|壞掉|502|500|bug|error|failure|stacktrace)", re.I),
    "規則詢問": re.compile(r"(SLA|條款|合約|規範|政策|policy|流程|SOP|FAQ)", re.I),
    "資料異動": re.compile(r"(更改|變更|修改|更新|異動|地址|電話|email|e-mail|帳號|個資|profile|變動)", re.I),
}

PRIORITY = PRIORITY  # 命中多類時的優先順序

def route_with_threshold(p):
    lab = p["pred_intent"]; conf = p.get("intent_conf", 0.0)
    thr = th.get(lab, th.get("其他", 0.40))
    return lab if conf >= thr else "其他"

def apply_rules(text, label, conf):
    """
    僅在 (label==其他) 或 (conf < 該類門檻) 時啟動規則回填；
    命中多個類時依 PRIORITY 選擇。
    """
    if text is None: text = ""
    triggers = [k for k,rx in RX.items() if rx.search(text)]
    if (label == "其他" or conf < th.get(label, th.get("其他",0.40))) and triggers:
        for k in PRIORITY:
            if k in triggers:
                return k, f"rule:{k}"
    return label, None

# 先門檻，再規則
gold = [d.get("intent") for d in ds]
pred = []
for d,p in zip(ds,pr):
    t_label = route_with_threshold(p)
    a_label, reason = apply_rules(__pick_text(d), t_label, p.get("intent_conf",0.0))
    pred.append(a_label)

# 指標（簡化計算）
labels = sorted(set(gold)|set(pred))
def prf(lbl):
    tp=sum(1 for g,y in zip(gold,pred) if g==lbl and y==lbl)
    fp=sum(1 for g,y in zip(gold,pred) if g!=lbl and y==lbl)
    fn=sum(1 for g,y in zip(gold,pred) if g==lbl and y!=lbl)
    P=tp/(tp+fp) if tp+fp>0 else 0.0
    R=tp/(tp+fn) if tp+fn>0 else 0.0
    F=2*P*R/(P+R) if P+R>0 else 0.0
    return P,R,F,tp,fp,fn

rows=[]
for L in labels:
    P,R,F,tp,fp,fn = prf(L)
    rows.append((L, round(P,3), round(R,3), round(F,3), tp, fp, fn))
macroF = round(sum(r[3] for r in rows)/len(rows), 3)

out = Path(INTENT_DIR)/"metrics_after_threshold_and_rules.md"
with open(out,"w",encoding="utf-8") as f:
    f.write("# Intent metrics (threshold + rules)\n")
    f.write(f"- thresholds: {json.dumps(th,ensure_ascii=False)}\n")
    f.write(f"- macro_f1_after_threshold_and_rules: {macroF}\n\n")
    f.write("|label|P|R|F1|TP|FP|FN|\n|---|---:|---:|---:|---:|---:|---:|\n")
    for L,P,R,F,tp,fp,fn in rows:
        f.write(f"|{L}|{P}|{R}|{F}|{tp}|{fp}|{fn}|\n")

print("[OK] write", out)
