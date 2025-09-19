from __future__ import annotations
import json, math, sqlite3, time
from pathlib import Path
from collections import Counter

OUT_DIR = Path("reports_auto/kie"); OUT_DIR.mkdir(parents=True, exist_ok=True)

def load_jsonl(p: Path):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]

def iou(a,b):
    s1,e1=a["start"],a["end"]; s2,e2=b["start"],b["end"]
    inter=max(0, min(e1,e2)-max(s1,s2)); union=max(e1,e2)-min(s1,s2)
    return (inter/union) if union>0 else 0.0

def match_counts(golds, preds, labels, overlap=False):
    TP=Counter(); FP=Counter(); FN=Counter()
    used=[False]*len(golds)
    for p in preds:
        lab=p["label"]; 
        if lab not in labels: 
            FP[lab]+=1; 
            continue
        best=-1.0; idx=-1
        for i,g in enumerate(golds):
            if used[i] or g["label"]!=lab: continue
            if overlap:
                score=iou(g,p)
                ok= score>0.0
                if ok and score>best: best=score; idx=i
            else:
                ok=(g["start"]==p["start"] and g["end"]==p["end"])
                if ok: idx=i; break
        if idx>=0:
            used[idx]=True; TP[lab]+=1
        else:
            FP[lab]+=1
    for i,g in enumerate(golds):
        if g["label"] in labels and not used[i]: FN[g["label"]]+=1
    return TP,FP,FN

def prf(TP,FP,FN):
    labs=sorted(set(TP)|set(FP)|set(FN))
    per={}
    for L in labs:
        tp,fp,fn=TP[L],FP[L],FN[L]
        P= tp/(tp+fp) if (tp+fp)>0 else 0.0
        R= tp/(tp+fn) if (tp+fn)>0 else 0.0
        F= (2*P*R/(P+R)) if (P+R)>0 else 0.0
        per[L]={"tp":tp,"fp":fp,"fn":fn,"precision":P,"recall":R,"f1":F}
    macro={"precision": sum(per[L]["precision"] for L in labs)/len(labs) if labs else 0.0,
           "recall":    sum(per[L]["recall"]    for L in labs)/len(labs) if labs else 0.0,
           "f1":        sum(per[L]["f1"]        for L in labs)/len(labs) if labs else 0.0}
    tp=sum(TP.values()); fp=sum(FP.values()); fn=sum(FN.values())
    microP= tp/(tp+fp) if (tp+fp)>0 else 0.0
    microR= tp/(tp+fn) if (tp+fn)>0 else 0.0
    microF= (2*microP*microR/(microP+microR)) if (microP+microR)>0 else 0.0
    micro={"precision":microP,"recall":microR,"f1":microF}
    return per, macro, micro, {"tp":tp,"fp":fp,"fn":fn}

def main():
    gold_p=Path("data/kie/test.jsonl")
    last_pred_p=Path("reports_auto/kie/_last_pred.txt")
    if not gold_p.exists() or not last_pred_p.exists():
        print("[KIE] no gold or pred"); return
    pred_p=Path(last_pred_p.read_text(encoding="utf-8").strip())
    gold_items=load_jsonl(gold_p); pred_items=load_jsonl(pred_p)
    # 只用 gold 出現的類別評分
    labels=sorted({s["label"] for o in gold_items for s in o.get("spans",[])})
    G=[s|{"_i":i} for i,o in enumerate(gold_items) for s in o.get("spans",[])]
    P=[s|{"_i":i} for i,o in enumerate(pred_items) for s in o.get("spans",[])]
    TP,FP,FN = match_counts([g for g in G], [p for p in P], labels, overlap=False)
    perE,macE,micE,supE = prf(TP,FP,FN)
    TP2,FP2,FN2 = match_counts([g for g in G], [p for p in P], labels, overlap=True)
    perO,macO,micO,supO = prf(TP2,FP2,FN2)
    out={
        "source":{"gold":str(gold_p),"pred":str(pred_p)},
        "exact":{"labels":labels,"per_label":perE,"macro":macE,"micro":micE,"support":supE},
        "overlap":{"labels":labels,"per_label":perO,"macro":macO,"micro":micO,"support":supO},
    }
    OUT_DIR.joinpath("metrics.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print("[KIE] metrics ->", OUT_DIR/"metrics.json")
    # 寫入 DB（kie_runs）
    db=Path("db/sma.sqlite"); db.parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(db); cur=con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS kie_runs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT, gold TEXT, pred TEXT,
      exact_micro_f1 REAL, overlap_micro_f1 REAL,
      exact_macro_f1 REAL, overlap_macro_f1 REAL
    )""")
    cur.execute("INSERT INTO kie_runs(ts,gold,pred,exact_micro_f1,overlap_micro_f1,exact_macro_f1,overlap_macro_f1) VALUES(?,?,?,?,?,?,?)",
      (time.strftime("%Y%m%dT%H%M%S"), str(gold_p), str(pred_p),
       out["exact"]["micro"]["f1"], out["overlap"]["micro"]["f1"], out["exact"]["macro"]["f1"], out["overlap"]["macro"]["f1"]))
    con.commit(); con.close()
if __name__=="__main__": main()
