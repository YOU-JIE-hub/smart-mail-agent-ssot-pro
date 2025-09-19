import json, os, re
from pathlib import Path
def load_jsonl(p):
    P=Path(p)
    if not P.exists(): return []
    out=[]
    for line in P.read_text("utf-8",errors="ignore").splitlines():
        try: out.append(json.loads(line))
        except: pass
    return out
def regex_parse_rate(texts):
    # 最小可解指標：金額/電話/單號
    amt=re.compile(r'(?:(?:NT\$|TWD|USD)\s?)?\d{1,3}(?:,\d{3})*(?:\.\d+)?')
    tel=re.compile(r'(?:\+?\d{1,3}[-\s]?)?(?:\d{2,4}[-\s]?)?\d{3,4}[-\s]?\d{3,4}')
    oid=re.compile(r'(?:PO|SO|INV|訂單|單號)[-\s:]?[\w\-]{4,}')
    n=len(texts); 
    if n==0: return {"regex_parse_rate":0,"n":0}
    c=sum(1 for t in texts if (amt.search(t or "") or tel.search(t or "") or oid.search(t or "")))
    return {"regex_parse_rate": round(c/n,4), "n": n}
root="models/kie"
reg=Path(root)/"registry.json"
out_dir=Path(f"{root}/artifacts/v{os.environ.get('TODAY','')}")
out_dir.mkdir(parents=True, exist_ok=True)
met=out_dir/"metrics.json"; card=out_dir/"MODEL_CARD.md"
res={"status":"skipped","reason":""}
try:
    # 檢查 bundle 與權重/tokenizer/config
    if not reg.exists(): res["reason"]="registry_missing"
    else:
        active=json.loads(reg.read_text("utf-8")).get("active")
        b=Path(root)/"artifacts"/active/"bundle"
        ok = b.exists() and any((b/"model"/x).exists() for x in ("model.safetensors","pytorch_model.bin","model.bin")) \
             and ( (b/"model/tokenizer.json").exists() or (b/"tokenizer.json").exists() ) \
             and ( (b/"model/config.json").exists() or (b/"config.json").exists() )
        # 先做「契約/可解析率」離線指標
        gold_candidates=[
            "data/kie_eval/gold_merged.jsonl",
            "/home/youjie/projects/smart-mail-agent_ssot/data/kie_eval/gold_merged.jsonl",
            "/home/youjie/projects/smart-mail-agent_ssot/data/kie/test_real.for_eval.jsonl"
        ]
        ds=[]
        for p in gold_candidates:
            ds=load_jsonl(p)
            if ds: break
        texts=[ (r.get("text") or r.get("content") or r.get("body") or "") for r in ds ]
        regz=regex_parse_rate(texts)
        res={"status":"ok","ready":bool(ok),**regz}
    met.write_text(json.dumps(res,ensure_ascii=False,indent=2),"utf-8")
    if not card.exists(): card.write_text(f"# Model Card — KIE (v{os.environ.get('TODAY','')})\n","utf-8")
    print("[kie.eval]",res["status"])
except Exception as e:
    met.write_text(json.dumps({"status":"error","error":str(e)},ensure_ascii=False,indent=2),"utf-8"); raise
