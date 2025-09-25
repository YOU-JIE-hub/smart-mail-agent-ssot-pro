#!/usr/bin/env python3
import os, sys, json, time, hashlib
from pathlib import Path
ROOT = Path(os.getcwd())
def read_dotenv(dotenv: Path) -> dict:
    env = {}
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8", errors="ignore").splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v = line.split("=",1); env[k.strip()] = v.strip().strip('"').strip("'")
    return env
def sha256_of(path: Path, max_bytes=16*1024*1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        if path.stat().st_size > max_bytes: h.update(f.read(max_bytes)); h.update(b"__TRUNC__")
        else:
            for chunk in iter(lambda: f.read(1<<20), b""): h.update(chunk)
    return h.hexdigest()
def file_stat(p: Path) -> dict:
    if p.is_file():
        return {"exists": True,"kind":"file","size": p.stat().st_size,"mtime": int(p.stat().st_mtime),"sha256_head16mb": sha256_of(p),"abspath": str(p.resolve())}
    if p.is_dir():
        items=list(p.iterdir()); return {"exists": True,"kind":"dir","count": len(items),"sample": sorted([x.name for x in items[:10]]),"abspath": str(p.resolve())}
    return {"exists": False,"kind":"missing","abspath": str(p)}
def try_introspect_intent_classes(p: Path) -> dict:
    info={"ok":False,"n_classes":None,"classes":None,"warn":None}
    try:
        import joblib
        obj=joblib.load(p)
        classes=None
        if hasattr(obj,"classes_"): classes=obj.classes_
        elif hasattr(obj,"named_steps"):
            for step in obj.named_steps.values():
                if hasattr(step,"classes_"): classes=step.classes_; break
        if classes is not None:
            info.update(ok=True,n_classes=len(list(classes)),classes=[str(x) for x in classes])
        else: info["warn"]="no classes_ found"
    except Exception as e:
        info["warn"]=f"introspect failed: {e.__class__.__name__}"
    return info
def main():
    ts=time.strftime("%Y%m%dT%H%M%S")
    outdir=ROOT/"reports_auto"/"status"; outdir.mkdir(parents=True, exist_ok=True)
    jpath=outdir/f"ENV_DOCTOR_{ts}.json"; mpath=outdir/f"ENV_DOCTOR_{ts}.md"
    dotenv=ROOT/".env"; env=read_dotenv(dotenv); merged=dict(os.environ); merged.update(env)
    keys=["INTENT_PKL","SPAM_PKL","KIE_DIR","INTENT_CLASSES_JSON"]; paths={}
    for k in keys:
        v=merged.get(k,""); 
        if not v: paths[k]={"exists":False,"kind":"unset","abspath":""}; continue
        p=Path(v); p=p if p.is_absolute() else ROOT/p; paths[k]=file_stat(p)
    intent_meta={}
    if paths["INTENT_PKL"].get("exists") and paths["INTENT_PKL"]["kind"]=="file":
        intent_meta=try_introspect_intent_classes(Path(paths["INTENT_PKL"]["abspath"]))
    risks=[]; suggestions=[]
    for k in ("INTENT_PKL","SPAM_PKL","KIE_DIR"):
        if not paths.get(k,{}).get("exists"):
            risks.append(f"{k} 未設定或不存在"); suggestions.append(f"請在 .env 設定 {k}=<路徑> 並確保存在")
    if paths["KIE_DIR"].get("exists") and paths["KIE_DIR"].get("kind")!="dir":
        risks.append("KIE_DIR 指向的不是資料夾"); suggestions.append("請將 KIE_DIR 指向包含模型權重的資料夾")
    if paths["INTENT_PKL"].get("exists") and paths["SPAM_PKL"].get("exists"):
        if paths["INTENT_PKL"]["abspath"]==paths["SPAM_PKL"]["abspath"]:
            risks.append("INTENT_PKL 與 SPAM_PKL 指向同一檔案"); suggestions.append("請為 Intent 與 Spam 使用不同模型檔")
    if intent_meta.get("ok") and intent_meta.get("n_classes",0)<2:
        risks.append("Intent 模型 classes_ 少於 2 類"); suggestions.append("請確認 INTENT_PKL 是否為多類權重")
    if not intent_meta.get("ok"):
        suggestions.append("若要在報表顯示類別清單，建議提供 INTENT_CLASSES_JSON 檔作備援")
    data={"ts":ts,"root":str(ROOT),"python": sys.version.split()[0],"dotenv": str(dotenv),
          "env_keys_present": {k:(k in merged and bool(merged[k])) for k in keys},
          "paths": paths,"intent_meta": intent_meta,"risks": risks,"suggestions": suggestions}
    jpath.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    md=[f"# Env Doctor @ {ts}\n\n",f"- 專案根：`{data['root']}`\n",f"- Python ：`{data['python']}`\n",f"- .env    ：`{data['dotenv']}`\n\n","## 關鍵路徑\n\n"]
    for k in keys:
        p=data["paths"].get(k,{})
        md+= [f"**{k}**  \n", f"`{p.get('abspath','')}`  \n", f"狀態：{p.get('kind')} / 存在={p.get('exists')}  \n"]
        if p.get("kind")=="file": md+= [f"大小：{p.get('size','?')}，sha256(head16MB)：`{p.get('sha256_head16mb','-')}`  \n"]
        if p.get("kind")=="dir":  md+= [f"項目數：{p.get('count','?')}，sample：`{','.join(p.get('sample',[]))}`  \n"]
        md+=["\n"]
    md+=["## Intent 模型摘要\n\n"]
    if data["intent_meta"].get("ok"):
        md+=[f"- 類別數：{data['intent_meta'].get('n_classes')}  \n",
             f"- 類別清單（前 20）：`{','.join(map(str, data['intent_meta'].get('classes',[])[:20]))}`  \n"]
    else:
        md+=[f"- 無法讀取 classes_：{data['intent_meta'].get('warn','unknown')}  \n"]
    md+=["\n## 風險\n\n"]; md+=([f"- {r}\n" for r in data["risks"]] or ["- （無）\n"])
    md+=["\n## 建議\n\n"]; md+=([f"- {s}\n" for s in data["suggestions"]] or ["- （無）\n"])
    (mpath).write_text("".join(md),encoding="utf-8")
    print(str(jpath)); print(str(mpath))
if __name__=="__main__": main()
