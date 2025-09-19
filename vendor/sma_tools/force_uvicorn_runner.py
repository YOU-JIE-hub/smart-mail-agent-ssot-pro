import os, sys, importlib.util, pathlib, faulthandler
faulthandler.enable(open("reports_auto/ERR/py_last_trace.txt","a"))
p = pathlib.Path(sys.argv[1])
port = int(os.environ.get("PORT","8000"))
spec = importlib.util.spec_from_file_location("sma_api_server_mod", str(p))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
app = getattr(mod, "app", None)
if app is None and hasattr(mod, "create_app"):
    app = mod.create_app()
if app is None:
    print("[WARN] no app/create_app; raw exec", file=sys.stderr)
    os.execvp(sys.executable, [sys.executable, "-u", str(p)])
else:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
