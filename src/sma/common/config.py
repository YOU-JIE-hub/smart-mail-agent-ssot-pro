import os, json, pathlib, hashlib

def _load_env(path=".env"):
    p=pathlib.Path(path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v=line.split("=",1); os.environ[k.strip()]=v.strip()
_load_env()

def env_path(key:str):
    v=os.getenv(key); 
    return pathlib.Path(v).expanduser().resolve() if v else None

def classes_fallback()->list[str]:
    raw=os.getenv("INTENT_CLASSES_JSON","[]")
    try:
        lst=json.loads(raw)
        return [str(x) for x in lst]
    except Exception:
        return []

def sha256_file(p: pathlib.Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
