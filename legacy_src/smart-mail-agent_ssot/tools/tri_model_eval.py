from __future__ import annotations
import json, time, os, re, statistics as stats
from pathlib import Path
from typing import Dict, Any, List, Tuple

ROOT = Path(os.environ.get("ROOT") or Path.cwd())
EVAL_OUT = ROOT/"reports_auto/eval"/time.strftime("%Y%m%dT%H%M%S")
EVAL_OUT.mkdir(parents=True, exist_ok=True)

def load_eval() -> List[Dict[str,Any]]:
    p = ROOT/"fixtures/eval_set.jsonl"
    return [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]

def load_contract() -> Dict[str,Any]:
    return json.loads((ROOT/"artifacts_prod/intent_contract.json").read_text(encoding="utf-8"))

# ---- Backends（先提供 rule；openai/local 留接口，現階段可 fallback 到 rule） ----
def backend_rule(email: Dict[str,Any], contract: Dict[str,Any]) -> Dict[str,Any]:
    from tools.pipeline_baseline import classify_rule, extract_slots_rule, plan_actions
    t0=time.time(); intent=classify_rule(email, contract); t1=time.time()
    slots=extract_slots_rule(email, intent); t2=time.time()
    actions=plan_actions(intent, slots); t3=time.time()
    return {"intent":intent,"slots":slots,"actions":actions,
            "latency_ms":{"classify":int((t1-t0)*1000),"extract":int((t2-t1)*1000),"plan":int((t3-t2)*1000)}}

def backend_local(email, contract):
    # TODO: 接入本地模型；暫時退回 rule
    return backend_rule(email, contract)

def backend_openai(email, contract):
    # TODO: 接入線上 LLM；若無金鑰或 SMA_OFFLINE=1 則退回 rule
    if os.environ.get("SMA_OFFLINE")=="1" or not os.environ.get("OPENAI_API_KEY"):
        return backend_rule(email, contract)
    return backend_rule(email, contract)

BACKENDS = {
    "rule": backend_rule,
    "local": backend_local,
    "openai": backend_openai,
}

def f1_from_counts(tp, fp, fn) -> float:
    if tp==0: return 0.0
    prec = tp/(tp+fp) if (tp+fp)>0 else 0
    rec  = tp/(tp+fn) if (tp+fn)>0 else 0
    return 2*prec*rec/(prec+rec) if (prec+rec)>0 else 0.0

def eval_backend(name: str) -> Dict[str,Any]:
    data = load_eval()
    contract = load_contract()
    cls = BACKENDS[name]
    tp=fp=fn=0
    lat_c, lat_e, lat_p = [],[],[]
    conf: Dict[Tuple[str,str], int] = {}
    for ex in data:
        out = cls(ex["email"], contract)
        y_true = ex["label_intent"]; y_pred = out["intent"]
        conf[(y_true, y_pred)] = conf.get((y_true,y_pred),0)+1
        if y_true==y_pred: tp+=1
        else: fp+=1; fn+=1
        lat = out.get("latency_ms",{})
        lat_c.append(lat.get("classify",0))
        lat_e.append(lat.get("extract",0))
        lat_p.append(lat.get("plan",0))
    acc = tp/len(data) if data else 0.0
    f1  = f1_from_counts(tp,fp,fn)
    rep = {
        "backend": name,
        "samples": len(data),
        "accuracy": round(acc,4),
        "f1_macro_like": round(f1,4),
        "latency_ms_p50": {
            "classify": int(stats.median(lat_c)) if lat_c else 0,
            "extract":  int(stats.median(lat_e)) if lat_e else 0,
            "plan":     int(stats.median(lat_p)) if lat_p else 0,
        },
        "confusion": [{"true":k[0],"pred":k[1],"n":v} for k,v in sorted(conf.items())]
    }
    (EVAL_OUT/f"report_{name}.json").write_text(json.dumps(rep,ensure_ascii=False,indent=2),encoding="utf-8")
    return rep

def main():
    results=[eval_backend(b) for b in ("rule","local","openai")]
    # 輸出一份 Markdown 彙總
    md=[ "# Tri-Stage / Tri-Model Eval",
         f"- dir: {EVAL_OUT}",
         "| backend | samples | acc | f1 | p50 classify(ms) | p50 extract | p50 plan |",
         "|---|---:|---:|---:|---:|---:|---:|" ]
    for r in results:
        md.append(f"| {r['backend']} | {r['samples']} | {r['accuracy']} | {r['f1_macro_like']} | "
                  f"{r['latency_ms_p50']['classify']} | {r['latency_ms_p50']['extract']} | {r['latency_ms_p50']['plan']} |")
    (EVAL_OUT/"SUMMARY.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))

if __name__=="__main__":
    main()
