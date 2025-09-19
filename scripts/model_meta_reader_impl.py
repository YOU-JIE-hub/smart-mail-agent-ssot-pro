from pathlib import Path
import json, hashlib, os, glob

def sha256_head(p,cap=4*1024*1024):
    p=Path(p); h=hashlib.sha256(); r=0
    with p.open("rb") as f:
        while True:
            b=f.read(1024*1024)
            if not b: break
            h.update(b); r+=len(b)
            if r>=cap: h.update(b"__TRUNCATED__"); break
    return h.hexdigest()

def read_kie_meta(root="models/kie"):
    root=Path(root); reg=root/"registry.json"
    if not reg.exists(): return {"source":"missing_registry"}
    active=(json.loads(reg.read_text("utf-8")) or {}).get("active")
    bundle=root/"artifacts"/(active or "")/"bundle"
    m={"source":"registry","version":active,"paths":{"bundle":bundle.as_posix()}}
    if not bundle.exists(): m["warning"]="bundle_missing"; return m
    # 搜索兩處：bundle/* 與 bundle/model/*（glob）
    def exists_any(names):
        hits=[]
        for n in names:
            for p in [bundle/b for b in ["", "model/"]]:
                q=p/n
                if q.exists(): hits.append(q)
        return hits
    weights=None
    for n in ("model.safetensors","pytorch_model.bin","model.bin"):
        hits=exists_any([n])
        if hits: weights=hits[0]; break
    tok_hits=[]
    for n in ("tokenizer.json","tokenizer_config.json","special_tokens_map.json","vocab.json","sentencepiece.bpe.model","spiece.model"):
        tok_hits+=exists_any([n])
    cfg_hits=[]
    for n in ("config.json","config.yaml","config.yml"):
        cfg_hits+=exists_any([n])
    m.update({"weights":weights.as_posix() if weights else None,
              "tokenizer_files":[h.as_posix() for h in tok_hits],
              "config_files":[h.as_posix() for h in cfg_hits]})
    if weights and weights.suffix==".safetensors":
        try: m["sha256_head"]=sha256_head(weights)
        except Exception as e: m["sha256_head_error"]=str(e)[:160]
    m["ready_flags"]={"has_weights":bool(weights),"has_tokenizer":bool(tok_hits),"has_config":bool(cfg_hits)}
    return m

def read_intent_meta():
    p=os.environ.get("SMA_INTENT_ML_PKL")
    m={"source":"legacy_env","path":p}
    try:
        if p and Path(p).exists(): m["sha256_head"]=sha256_head(p)
    except Exception as e: m["sha256_head_error"]=str(e)[:160]
    return m

def read_spam_meta():
    p=os.environ.get("SMA_SPAM_ML_PKL","/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/77/77/artifacts_sa/spam_rules_lr.pkl")
    m={"source":"legacy_env_or_default","path":p}
    try:
        if p and Path(p).exists(): m["sha256_head"]=sha256_head(p)
    except Exception as e: m["sha256_head_error"]=str(e)[:160]
    return m
