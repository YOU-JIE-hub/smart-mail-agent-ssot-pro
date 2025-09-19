#!/usr/bin/env python3
import os, sys, faulthandler, signal, runpy, traceback
RUN = os.environ.get("SMA_RUN_DIR", "."); os.makedirs(RUN, exist_ok=True)
out_path  = os.path.join(RUN, "api.out")
err_path  = os.path.join(RUN, "api.err")
trace_path= os.path.join(RUN, "api.trace")
pid_path  = os.path.join(RUN, "api.pid")
so = open(out_path, "ab", buffering=0); se = open(err_path, "ab", buffering=0)
os.dup2(so.fileno(), 1); os.dup2(se.fileno(), 2)
sys.stdout = os.fdopen(1, "wb", buffering=0)
sys.stderr = os.fdopen(2, "wb", buffering=0)
tf = open(trace_path, "ab", buffering=0)
faulthandler.enable(file=tf, all_threads=True)
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGSEGV, signal.SIGABRT,
            getattr(signal, "SIGBUS", None), getattr(signal, "SIGILL", None),
            getattr(signal, "SIGFPE", None)):
    if sig is not None:
        try: faulthandler.register(sig, file=tf, all_threads=True)
        except Exception: pass
with open(pid_path, "w") as f: f.write(str(os.getpid()))
entry = os.environ.get("SMA_ENTRY", "tools.api_server")
try:
    runpy.run_module(entry, run_name="__main__")
except BaseException:
    traceback.print_exc()
    raise
