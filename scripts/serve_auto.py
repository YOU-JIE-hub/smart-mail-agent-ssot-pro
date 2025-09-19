import importlib, inspect, os, sys, time
from pathlib import Path
PORT=int(os.environ.get("PORT","8088"))
MODULE=os.environ.get("SMA_API_MODULE","tools.api_server")
print(f"[serve_auto] module={MODULE} port={PORT}")
try:
    mod=importlib.import_module(MODULE)
except Exception as e:
    print("[serve_auto] import failed:", e); sys.exit(2)
# 找出 FastAPI 實例：屬性是 FastAPI 或名稱常見（app/api）
app_obj=None
try:
    from fastapi import FastAPI
    for name,val in vars(mod).items():
        if isinstance(val, FastAPI) or name in {"app","api","application","server"}:
            app_obj=val if not isinstance(val,str) else None
            if app_obj is not None: target=name; break
except Exception:
    app_obj=None
if app_obj is None:
    # 再試：模組具有 get_app()/create_app() 工廠
    for fn in ("get_app","create_app"): 
        if hasattr(mod, fn): 
            cand=getattr(mod, fn)()
            app_obj=cand; target=fn
            break
if app_obj is None:
    print("[serve_auto] no FastAPI app found; creating fallback")
    from fastapi import FastAPI
    app_obj=FastAPI(title="SMA Fallback")
    @app_obj.get("/debug/model_meta")
    def meta(): return {"intent":{"version":"legacy","metrics":{}},"spam":{"version":"legacy","metrics":{}},"kie":{"version":"legacy","metrics":{}}}
    @app_obj.post("/classify")
    def cls(x:dict): 
        t=(x.get("text") or "").lower(); lab="biz_quote" if ("quote" in t or "報價" in t) else "other"; 
        return {"label":lab,"proba":0.9 if lab=="biz_quote" else 0.6,"route":x.get("route","rule")}
    @app_obj.post("/extract")
    def ex(x:dict): 
        import re; s=x.get("text") or ""; ph=re.findall(r"(?:\\+?\\d{1,3}[-\\s]?)?(?:\\d{2,4}[-\\s]?)?\\d{3,4}[-\\s]?\\d{3,4}", s); 
        am=re.findall(r"\\b\\d{1,3}(?:,\\d{3})*|\\b\\d+\\b", s); 
        return {"fields":{"phone":ph[:1] or None, "amount":am[:1] or None}}
    target="fallback_app"
print(f"[serve_auto] target={target}")
from uvicorn import Config, Server
cfg=Config(app_obj, host="127.0.0.1", port=PORT, log_level="info")
Server(cfg).run()
