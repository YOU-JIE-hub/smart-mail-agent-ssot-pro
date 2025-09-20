from __future__ import annotations
import os, json, pathlib, typing as T
from types import SimpleNamespace
ROOT = pathlib.Path(__file__).resolve().parents[1]

def _exists(p: T.Optional[str]) -> T.Optional[str]:
    if not p: return None
    try:
        pp = pathlib.Path(p).expanduser()
        return str(pp.resolve()) if pp.exists() else None
    except Exception:
        return None

def _parse_env_file(fp: pathlib.Path) -> dict:
    d={}
    for ln in fp.read_text(encoding="utf-8").splitlines():
        ln=ln.strip()
        if not ln or ln.startswith("#"): continue
        if "=" in ln:
            k,v = ln.split("=",1)
            d[k.strip()] = v.strip().strip('"').strip("'")
    return d

def get_model_paths(cfg_path: str | None = None):
    # defaults（若沒設環境變數就用專案內預設路徑）
    d = {
        "intent_pkl": _exists(os.environ.get("INTENT_PKL")) or _exists(str(ROOT/"models/intent/artifacts/model_pipeline.pkl")),
        "spam_pkl":   _exists(os.environ.get("SPAM_PKL"))   or _exists(str(ROOT/"models/spam/artifacts/model_pipeline.pkl")),
        "kie_dir":    os.environ.get("KIE_DIR") or None,
    }
    # optional config 檔（ENV 優先）
    if cfg_path:
        fp = pathlib.Path(cfg_path)
        if fp.exists():
            low = fp.suffix.lower()
            try:
                if low == ".env":
                    envd = _parse_env_file(fp)
                    d.update({
                        "intent_pkl": _exists(envd.get("INTENT_PKL")) or d["intent_pkl"],
                        "spam_pkl":   _exists(envd.get("SPAM_PKL"))   or d["spam_pkl"],
                        "kie_dir":    envd.get("KIE_DIR") or d["kie_dir"],
                    })
                elif low in {".json"}:
                    j=json.loads(fp.read_text(encoding="utf-8")) or {}
                    for k in ("intent_pkl","spam_pkl","kie_dir"):
                        if k in j: d[k] = _exists(j[k]) if k!="kie_dir" else j[k]
                else:
                    try:
                        import yaml  # type: ignore
                        j=yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
                        for k in ("intent_pkl","spam_pkl","kie_dir"):
                            if k in j: d[k] = _exists(j[k]) if k!="kie_dir" else j[k]
                    except Exception:
                        pass
            except Exception:
                pass
    # 讓呼叫端同時支援 attrs 和 dict 存取
    class Paths(dict):
        __getattr__ = dict.get
    return Paths(d)
