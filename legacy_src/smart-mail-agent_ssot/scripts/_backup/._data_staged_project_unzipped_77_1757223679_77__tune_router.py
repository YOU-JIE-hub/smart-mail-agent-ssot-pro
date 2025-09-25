#!/usr/bin/env python3
import json, os, pickle
def main():
    cfgp=".sma_tools/router_config.json"
    model="artifacts/intent_svm_plus_auto_cal.pkl"
    if not os.path.exists(model): model="artifacts/intent_svm_plus_auto.pkl"
    labels=[]
    if os.path.exists(model):
        with open(model,"rb") as f:
            labels=[str(x) for x in pickle.load(f)["clf"].classes_]
    cfg={}
    if os.path.exists(cfgp):
        try:
            with open(cfgp,"r",encoding="utf-8") as f: cfg=json.load(f)
        except Exception:
            cfg={}
    for lab in labels: cfg.setdefault(lab,0.5)
    with open(cfgp,"w",encoding="utf-8") as f: json.dump(cfg,f,ensure_ascii=False,indent=2)
    print("[TUNE] router_config.json updated")
if __name__=="__main__": main()
