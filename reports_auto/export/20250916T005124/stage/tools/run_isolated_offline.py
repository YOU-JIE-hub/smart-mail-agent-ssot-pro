#!/usr/bin/env python3
import os, sys, time, runpy, faulthandler, socket
from pathlib import Path

# ---- 強制離線與安全降級 ----
os.environ.setdefault("SMA_SMTP_MODE", "outbox")   # 一律寫 outbox，不連外
os.environ.setdefault("SMA_LLM_PROVIDER", "none") # 關閉 LLM/RAG provider
os.environ.setdefault("OPENAI_API_KEY", "")       # 禁用 OpenAI
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "")   # 避免某些 SSL 阻滯
os.environ.setdefault("NO_PROXY", "*")

# ---- 阻斷所有 socket 連接（防止任何連網卡死）----
def _block(*a, **k):  # noqa
    raise RuntimeError("Network disabled by tools/run_isolated_offline.py")
socket.socket.connect = (lambda orig: (lambda self, addr: _block()))(socket.socket.connect)  # type: ignore
try:
    import socket as _s
    _s.create_connection = lambda *a, **k: _block()  # type: ignore
except Exception:
    pass

# ---- faulthandler：150s 後自動傾印堆疊 ----
log_dir = Path("reports_auto/logs"); log_dir.mkdir(parents=True, exist_ok=True)
ts = time.strftime("%Y%m%dT%H%M%S")
fh_path = log_dir / f"faulthandler_{ts}.log"
fh = open(fh_path, "w")
faulthandler.enable(fh)
faulthandler.dump_traceback_later(150, repeat=False)

# ---- 轉交執行（支援跑檔案或模組）----
if len(sys.argv) < 2:
    print("Usage: run_isolated_offline.py <entry.py|module> [args...]", file=sys.stderr)
    sys.exit(2)

entry = sys.argv[1]
args = sys.argv[2:]
sys.argv = [entry] + args  # 傳遞給目標

# 讓下游可以知道目前 run_ts（給 out 路徑拼接也行）
os.environ.setdefault("SMA_RUN_TS", ts)

if entry.endswith(".py") and Path(entry).exists():
    runpy.run_path(entry, run_name="__main__")
else:
    runpy.run_module(entry, run_name="__main__")
