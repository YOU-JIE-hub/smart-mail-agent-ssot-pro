import faulthandler, sys, atexit, os
err_path = os.environ.get("SMA_CRASH_PY_TRACE", "py_last_trace.txt")
try:
    f = open(err_path, "w", encoding="utf-8", errors="backslashreplace")
    faulthandler.enable(file=f, all_threads=True)
except Exception:
    faulthandler.enable()  # fallback to stderr
def _excepthook(etype, e, tb):
    import traceback, datetime
    with open(err_path, "a", encoding="utf-8", errors="backslashreplace") as g:
        g.write(f"\n=== UNCAUGHT @ {datetime.datetime.now().isoformat()} ===\n")
        traceback.print_exception(etype, e, tb, file=g)
    sys.__excepthook__(etype, e, tb)
sys.excepthook = _excepthook
atexit.register(lambda: None)
