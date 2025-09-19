#!/usr/bin/env python3
# 三模型評估（小樣本強化版）：即使資料極少也會產出佔位圖與可讀報告
import os, sys, json, re, uuid, time, math, traceback
from pathlib import Path
from datetime import datetime
from email import policy
from email.parser import BytesParser

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, precision_recall_fscore_support,
                             roc_auc_score, average_precision_score,
                             confusion_matrix)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.getenv("SMA_ROOT", os.path.expanduser("~/projects/smart-mail-agent_ssot"))
OUT_BASE = Path(ROOT) / "reports_auto" / "eval"
LOG_PATH = Path(ROOT) / "reports_auto" / "logs" / "pipeline.ndjson"

INTENT_LABELS = ["報價", "技術支援", "投訴", "規則詢問", "資料異動", "其他"]

def log_event(kind, **kw):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    kw.update(ts=datetime.utcnow().isoformat(timespec="seconds")+"Z", kind=kind)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")

def parse_eml(p: Path):
    with open(p, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    subject = msg["subject"] or ""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_content(); break
    else:
        body = msg.get_content()
    text = f"{subject}\n{body}"
    return subject, body, text

# 佔位圖：資料不足也要有輸出
def placeholder_plot(path: Path, title: str, reason: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.figure()
    plt.title(title)
    plt.text(0.5, 0.5, reason, ha="center", va="center")
    plt.axis("off")
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()

def load_spam():
    mp = Path(ROOT) / "artifacts_prod" / "model_pipeline.pkl"
    thp = Path(ROOT) / "artifacts_prod" / "ens_thresholds.json"
    if mp.exists() and thp.exists():
        try:
            import joblib
            model = joblib.load(mp)
            th = json.load(open(thp, "r", encoding="utf-8"))
            thresh = float(th.get("spam", 0.5))
            return ("real", model, thresh)
        except Exception as e:
            log_event("warn", component="spam_loader", error=repr(e))
    return ("stub", None, 0.6)

SPAM_HINTS = ["unsubscribe", "點此", "點擊這裡", "限時優惠", "中獎", "免費", "保證", "bitcoin", "比特幣"]
def spam_predict(text, ctx):
    mode, model, thresh = ctx
    if mode == "real":
        try:
            prob = float(model.predict_proba([text])[0][-1])
            return prob
        except Exception as e:
            log_event("warn", component="spam_infer", error=repr(e))
    score = sum(1 for k in SPAM_HINTS if k in text.lower())
    prob = min(0.2 + 0.35*score, 0.99)
    return prob

def load_intent():
    mp = Path(ROOT) / "artifacts" / "intent_pro_cal.pkl"
    thp = Path(ROOT) / "reports_auto" / "intent_thresholds.json"
    model, lbls, th_map = None, INTENT_LABELS, {}
    mode = "stub"
    if mp.exists():
        try:
            import joblib, numpy as np  # noqa
            model = joblib.load(mp)
            lbls = list(getattr(model, "classes_", INTENT_LABELS))
            mode = "real"
        except Exception as e:
            log_event("warn", component="intent_loader", error=repr(e))
    if thp.exists():
        try:
            th_map = json.load(open(thp, "r", encoding="utf-8"))
        except Exception as e:
            log_event("warn", component="intent_thresholds", error=repr(e))
    return (mode, model, lbls, th_map)

def intent_predict(text, ctx):
    mode, model, lbls, th_map = ctx
    if mode == "real" and model is not None:
        try:
            probs = model.predict_proba([text])[0]
            i = int(np.argmax(probs))
            label = str(lbls[i]); conf = float(probs[i])
            return label, conf
        except Exception as e:
            log_event("warn", component="intent_infer", error=repr(e))
    rules = {
        "報價": ["報價", "quote", "報價單", "價格", "估價"],
        "技術支援": ["無法登入", "錯誤", "bug", "error", "支援", "故障"],
        "投訴": ["抱怨", "投訴", "不滿", "客訴"],
        "規則詢問": ["如何", "可否", "流程", "規則", "policy", "條款", "FAQ", "faq"],
        "資料異動": ["變更", "更新資料", "修改地址", "電話變更", "個資"],
    }
    for k, kws in rules.items():
        if any(kw.lower() in text.lower() for kw in kws):
            return k, 0.85
    return "其他", 0.35

# KIE：若 kie/infer.py 有 extract(text) 就用，否則規則
def kie_extract(text: str):
    try:
        import importlib.util
        ip = Path(ROOT)/"kie"/"infer.py"
        if ip.exists():
            spec = importlib.util.spec_from_file_location("kie_infer", ip)
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            if hasattr(mod, "extract"):
                return mod.extract(text)
    except Exception as e:
        log_event("warn", component="kie_loader", error=repr(e))
    spans=[]
    m = re.search(r"(20\d{2}[-/\.](0?[1-9]|1[0-2])[-/\.](0?[1-9]|[12]\d|3[01]))", text)
    if m: spans.append(("date_time", m.group(1), m.start(), m.end()))
    m = re.search(r"(NTD|NT\$|\$)\s?([0-9]{1,3}(,[0-9]{3})*(\.[0-9]+)?|[0-9]+(\.[0-9]+)?)", text)
    if m: spans.append(("amount", m.group(0), m.start(), m.end()))
    for env in ["prod", "staging", "dev", "UAT", "uat"]:
        i = text.lower().find(env.lower())
        if i >= 0: spans.append(("env", env, i, i+len(env)))
    m = re.search(r"(\d+)\s*(hours|hrs|days|天|小時)", text, re.I)
    if m: spans.append(("sla", m.group(0), m.start(), m.end()))
    return spans

# 正規化（KIE 比對）
def norm_date(s):
    s=str(s); s=s.replace(".","-").replace("/","-")
    m=re.match(r"(20\d{2})-(\d{1,2})-(\d{1,2})", s)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s.strip()
def norm_amount(s):
    s=str(s).replace(",","").replace("NTD","").replace("NT$","").replace("$","").strip()
    try: return str(float(s))
    except: return s
def norm_env(s): return str(s).strip().lower()
def norm_sla(s): return re.sub(r"\s+","",str(s)).lower()

def eval_kie(pred_spans, gold):
    keys = ["date_time","amount","env","sla"]
    norms = {"date_time":norm_date,"amount":norm_amount,"env":norm_env,"sla":norm_sla}
    res={}
    micro_tp=micro_fp=micro_fn=0
    for k in keys:
        pset={norms[k](v) for kk,v,_,__ in pred_spans if kk==k}
        gset={norms[k](v) for v in gold.get(k,[])} if gold else set()
        tp=len(pset & gset); fp=len(pset-gset); fn=len(gset-pset)
        prec=tp/(tp+fp) if tp+fp>0 else 0.0
        rec =tp/(tp+fn) if tp+fn>0 else 0.0
        f1 =2*prec*rec/(prec+rec) if prec+rec>0 else 0.0
        res[k]={"precision":prec,"recall":rec,"f1":f1,"tp":tp,"fp":fp,"fn":fn}
        micro_tp+=tp; micro_fp+=fp; micro_fn+=fn
    p = micro_tp/(micro_tp+micro_fp) if micro_tp+micro_fp>0 else 0.0
    r = micro_tp/(micro_tp+micro_fn) if micro_tp+micro_fn>0 else 0.0
    f = 2*p*r/(p+r) if p+r>0 else 0.0
    res["_micro"]={"precision":p,"recall":r,"f1":f,"tp":micro_tp,"fp":micro_fp,"fn":micro_fn}
    return res

def risk_coverage(top1_conf, correct_mask, grid=None):
    if grid is None: grid = np.linspace(0.0, 1.0, 101)
    pts=[]
    for thr in grid:
        decided = top1_conf>=thr
        cov = float(decided.mean())
        if cov>0:
            risk = 1.0 - float((correct_mask & decided).sum()/decided.sum())
        else:
            risk = 0.0
        pts.append((cov, risk))
    pts=sorted(pts, key=lambda x:x[0])
    covs=[c for c,_ in pts]; risks=[r for _,r in pts]
    aurc = float(np.trapz(risks, covs))
    return pts, aurc

def load_dataset(ds_path: Path):
    items=[]
    jl = ds_path/"labels.jsonl"
    if jl.exists():
        for line in open(jl,"r",encoding="utf-8"):
            if not line.strip(): continue
            obj=json.loads(line)
            p = ds_path/obj["eml"] if not os.path.isabs(obj["eml"]) else Path(obj["eml"])
            items.append({"path":p, "y_spam":int(obj.get("spam",0)),
                          "y_intent":obj.get("intent"), "y_kie":obj.get("kie",{})})
        return items
    for cand in ["dataset.jsonl","data.jsonl","labels.jsonl"]:
        jp = ds_path/cand
        if jp.exists():
            for line in open(jp,"r",encoding="utf-8"):
                if not line.strip(): continue
                o=json.loads(line)
                items.append({"text":o.get("text",""),
                              "y_spam":int(o.get("spam",0)),
                              "y_intent":o.get("intent"),
                              "y_kie":o.get("kie",{})})
            return items
    raise SystemExit(f"[FATAL] dataset not found: {ds_path}/labels.jsonl or dataset.jsonl")

def main():
    ds = Path(sys.argv[1]) if len(sys.argv)>1 else Path(ROOT)/"data"/"eval_demo"
    ts=time.strftime("%Y%m%dT%H%M%S")
    out_dir = OUT_BASE/ts; (out_dir/"plots").mkdir(parents=True, exist_ok=True)
    err_fp = open(out_dir/"eval_errors.ndjson","w",encoding="utf-8")
    pred_fp= open(out_dir/"eval_pred.jsonl","w",encoding="utf-8")

    log_event("eval_start", dataset=str(ds), out=str(out_dir))
    spam_ctx = load_spam()
    intent_ctx = load_intent()

    items = load_dataset(ds)
    y_spam=[]; s_score=[]
    y_intent=[]; p_intent=[]; p_conf=[]; correct=[]
    kie_accum={"per_item":[], "per_key":{}}

    for it in items:
        try:
            if "text" in it:
                text = it["text"]
            else:
                _,__,text = parse_eml(it["path"])
            sprob = spam_predict(text, spam_ctx)
            y_spam.append(int(it["y_spam"])); s_score.append(float(sprob))
            plabel, pconf = intent_predict(text, intent_ctx)
            y = it.get("y_intent")
            if y is not None:
                y_intent.append(y); p_intent.append(plabel); p_conf.append(pconf); correct.append(int(plabel==y))
            spans = kie_extract(text)
            kie_res = eval_kie(spans, it.get("y_kie",{}))
            kie_accum["per_item"].append({"res":kie_res})
            pred_fp.write(json.dumps({"spam_prob":sprob, "pred_intent":plabel, "intent_conf":pconf, "kie":spans}, ensure_ascii=False)+"\n")
        except Exception as e:
            err_fp.write(json.dumps({"err":repr(e)})+"\n")

    # Spam metrics
    spam_metrics={}
    y_spam = np.array(y_spam); s_score=np.array(s_score)
    thr=spam_ctx[2]; y_pred = (s_score>=thr).astype(int)
    spam_metrics["threshold"]=thr
    spam_metrics["acc"]=float(accuracy_score(y_spam,y_pred))
    pr,rc,f1,_ = precision_recall_fscore_support(y_spam,y_pred,average="binary",zero_division=0)
    spam_metrics.update(precision=float(pr), recall=float(rc), f1=float(f1))

    # 圖：若單一類，仍產出佔位圖並給說明
    from sklearn.metrics import roc_curve, precision_recall_curve
    if len(np.unique(y_spam))==2:
        spam_metrics["roc_auc"]=float(roc_auc_score(y_spam,s_score))
        spam_metrics["pr_auc"]=float(average_precision_score(y_spam,s_score))
        fpr,tpr,_=roc_curve(y_spam,s_score)
        prec,rec,_=precision_recall_curve(y_spam,s_score)
        plt.figure(); plt.plot(fpr,tpr); plt.xlabel("FPR"); plt.ylabel("TPR"); plt.title("Spam ROC")
        (out_dir/"plots").mkdir(exist_ok=True, parents=True)
        plt.savefig(out_dir/"plots"/"spam_roc.png", dpi=120); plt.close()
        plt.figure(); plt.plot(rec,prec); plt.xlabel("Recall"); plt.ylabel("Precision"); plt.title("Spam PR")
        plt.savefig(out_dir/"plots"/"spam_pr.png", dpi=120); plt.close()
    else:
        placeholder_plot(out_dir/"plots"/"spam_roc.png", "Spam ROC", "資料僅含單一類，無法計算 ROC/AUC")
        placeholder_plot(out_dir/"plots"/"spam_pr.png",  "Spam PR",  "資料僅含單一類，無法計算 PR/AUC")

    # Intent metrics
    intent_metrics={}
    if y_intent:
        y_true=np.array(y_intent); y_hat=np.array(p_intent)
        labels=sorted(set(list(y_true)+list(y_hat)))
        intent_metrics["labels"]=labels
        intent_metrics["acc"]=float(accuracy_score(y_true,y_hat))
        pr,rc,f1,sup = precision_recall_fscore_support(y_true,y_hat,labels=labels,zero_division=0)
        intent_metrics["per_class"]={lab:{"precision":float(pr[i]),"recall":float(rc[i]),"f1":float(f1[i]),"support":int(sup[i])} for i,lab in enumerate(labels)}
        mpr,mrc,mf1,_=precision_recall_fscore_support(y_true,y_hat,average="macro",zero_division=0)
        wpr,wrc,wf1,_=precision_recall_fscore_support(y_true,y_hat,average="weighted",zero_division=0)
        intent_metrics.update(macro={"precision":float(mpr),"recall":float(mrc),"f1":float(mf1)},
                              weighted={"precision":float(wpr),"recall":float(wrc),"f1":float(wf1)})

        # 混淆矩陣與支援度圖
        cm = confusion_matrix(y_true,y_hat,labels=labels)
        plt.figure(); plt.imshow(cm, interpolation="nearest")
        plt.xticks(range(len(labels)), labels, rotation=45, ha="right")
        plt.yticks(range(len(labels)), labels)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(j,i,str(cm[i,j]), ha="center", va="center")
        plt.title("Intent Confusion Matrix"); plt.xlabel("Pred"); plt.ylabel("Gold")
        plt.tight_layout(); plt.savefig(out_dir/"plots"/"intent_cm.png", dpi=120); plt.close()

        # 支援度長條圖：小樣本也能看出金標/預測分佈
        gold_counts = pd.Series(y_true).value_counts().reindex(labels, fill_value=0)
        pred_counts = pd.Series(y_hat).value_counts().reindex(labels, fill_value=0)
        plt.figure()
        x = np.arange(len(labels)); w=0.35
        plt.bar(x-w/2, gold_counts.values, width=w, label="gold")
        plt.bar(x+w/2, pred_counts.values, width=w, label="pred")
        plt.xticks(x, labels, rotation=45, ha="right"); plt.legend()
        plt.title("Intent Support (gold vs pred)"); plt.tight_layout()
        plt.savefig(out_dir/"plots"/"intent_support.png", dpi=120); plt.close()

        # 風險–覆蓋率
        top1=np.array([float(c) for c in p_conf]) if p_conf else np.array([])
        correct_mask=np.array([bool(c) for c in correct]) if correct else np.array([])
        if len(top1)>0 and len(correct_mask)>0:
            pts, aurc = risk_coverage(top1, correct_mask)
            intent_metrics["risk_coverage"]={"aurc":float(aurc), "points":[{"coverage":float(c),"risk":float(r)} for c,r in pts]}
            pd.DataFrame(intent_metrics["risk_coverage"]["points"]).to_csv(out_dir/"risk_coverage.csv", index=False)
        else:
            intent_metrics["risk_coverage"]={"aurc":None, "points":[]}
            pd.DataFrame([], columns=["coverage","risk"]).to_csv(out_dir/"risk_coverage.csv", index=False)

        # 門檻路由
        th_map = intent_ctx[3] if isinstance(intent_ctx, (list,tuple)) else {}
        if p_conf:
            decided = np.array([conf >= float(th_map.get(lbl,0.5)) for lbl,conf in zip(p_intent,p_conf)])
            if decided.any():
                sel_acc = float((y_hat[decided]==y_true[decided]).mean())
                intent_metrics["threshold_decision"]={"coverage":float(decided.mean()), "selective_accuracy":sel_acc}
            else:
                intent_metrics["threshold_decision"]={"coverage":0.0, "selective_accuracy":None}

    # KIE metrics（micro 與每 key）
    kie_tot={"tp":0,"fp":0,"fn":0}; kie_keys={}
    for rec in kie_accum["per_item"]:
        for k,v in rec["res"].items():
            if k=="_micro": continue
            a=kie_keys.setdefault(k,{"tp":0,"fp":0,"fn":0})
            a["tp"]+=v["tp"]; a["fp"]+=v["fp"]; a["fn"]+=v["fn"]
            kie_tot["tp"]+=v["tp"]; kie_tot["fp"]+=v["fp"]; kie_tot["fn"]+=v["fn"]
    def prf(a):
        p=a["tp"]/(a["tp"]+a["fp"]) if a["tp"]+a["fp"]>0 else 0.0
        r=a["tp"]/(a["tp"]+a["fn"]) if a["tp"]+a["fn"]>0 else 0.0
        f=2*p*r/(p+r) if p+r>0 else 0.0
        return p,r,f
    kie_metrics={"per_key":{}, "_micro":{}}
    for k,a in kie_keys.items():
        p,r,f = prf(a)
        kie_metrics["per_key"][k]={"precision":p,"recall":r,"f1":f,**a}
    p,r,f = prf(kie_tot)
    kie_metrics["_micro"]={"precision":p,"recall":r,"f1":f,**kie_tot}

    # 寫檔
    out = {"spam": spam_metrics, "intent": intent_metrics, "kie": kie_metrics, "dataset_size": len(items), "ts": ts}
    with open(out_dir/"metrics.json","w",encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=2)

    # 報告：加入診斷與建議
    diag=[]
    if len(items)<30: diag.append(f"- Dataset size 僅 {len(items)}，建議至少 30–50 筆再看 AUC/宏 F1。")
    if "intent" in out and out["intent"].get("labels")==["報價"]:
        diag.append("- Intent 僅 1 類，無法檢視跨類混淆；建議每類至少 20 筆。")
    if len(np.unique(y_spam))<2:
        diag.append("- Spam 僅單一類樣本，ROC/PR 僅輸出佔位圖。")
    lines = [f"# Eval Summary ({ts})",
             f"- Dataset size: {len(items)}",
             "## Diagnostics"] + (diag or ["- 無"])
    lines += ["## Spam",
              f"- acc={spam_metrics.get('acc'):.3f} f1={spam_metrics.get('f1'):.3f} thr={spam_metrics.get('threshold')}"]
    lines += [f"- roc_auc={spam_metrics.get('roc_auc', float('nan')):.3f} pr_auc={spam_metrics.get('pr_auc', float('nan')):.3f}"]
    lines += ["## Intent"]
    if out.get("intent"):
        im=out["intent"]
        lines += [f"- acc={im.get('acc', float('nan')):.3f} macro_f1={im.get('macro',{}).get('f1', float('nan')):.3f}"]
        td=im.get("threshold_decision",{})
        lines += [f"- threshold_decision: coverage={td.get('coverage', float('nan'))}, selective_acc={td.get('selective_accuracy', 'NA')}"]
        rc=im.get("risk_coverage",{}); lines += [f"- risk-coverage AURC={rc.get('aurc','NA')}"]
    lines += ["## KIE",
              f"- micro: P={out['kie']['_micro']['precision']:.3f} R={out['kie']['_micro']['recall']:.3f} F1={out['kie']['_micro']['f1']:.3f}"]
    (out_dir/"metrics.md").write_text("\n".join(lines), encoding="utf-8")

    log_event("eval_done", out=str(out_dir))
    print(f"[OK] Eval 完成 → {out_dir}")

if __name__=="__main__":
    main()
