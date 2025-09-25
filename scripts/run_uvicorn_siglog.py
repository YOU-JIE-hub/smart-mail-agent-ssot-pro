#!/usr/bin/env python3
import os, signal, datetime, pathlib, faulthandler

LOGD = pathlib.Path("reports_auto/serve/diag")
LOGD.mkdir(parents=True, exist_ok=True)
ts   = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
LOGF = LOGD / f"signal.{ts}.log"

def log(msg: str):
    with LOGF.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")

def dump(reason: str):
    log(f"[{datetime.datetime.utcnow().isoformat()}Z] SIGNAL reason={reason}")
    log(f"PID={os.getpid()} PPID={os.getppid()} CWD={os.getcwd()}")
    for k in ("INTENT_PKL","SPAM_PKL","PORT"):
        log(f"{k}={os.environ.get(k)}")
    try:
        with open(f"/proc/{os.getpid()}/status", "r") as s:
            log("--- /proc/self/status ---"); log(s.read())
    except Exception as e:
        log(f"(status fail: {e})")
    try:
        with open(f"/proc/{os.getppid()}/cmdline","rb") as c:
            cmd = " ".join(c.read().decode(errors="ignore").split("\x00")).strip()
            log(f"PPID_CMD={cmd}")
    except Exception as e:
        log(f"(ppid cmdline fail: {e})")
    log("--- STACKS ---")
    with LOGF.open("a", encoding="utf-8") as f:
        faulthandler.dump_traceback(file=f, all_threads=True)
    log("== END ==")

def _h(sig, frame): dump(f"signal={sig}")

for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
    try: signal.signal(s, _h)
    except Exception: pass

if __name__ == "__main__":
    env_file = os.environ.get("ENV_FILE",".env")
    # 可選載入 .env（沒有 python-dotenv 也沒關係）
    try:
        from dotenv import load_dotenv
        if os.path.exists(env_file): load_dotenv(env_file)
    except Exception:
        pass
    host = os.environ.get("HOST","127.0.0.1")
    port = int(os.environ.get("PORT","8000"))
    print(f"[SIGLOG] logging to: {LOGF}", flush=True)
    print(f"[SIGLOG] starting uvicorn on {host}:{port}", flush=True)
    import uvicorn
    uvicorn.run("service.app:app", host=host, port=port, log_level="info")
    print("[SIGLOG] uvicorn.run() returned", flush=True)
