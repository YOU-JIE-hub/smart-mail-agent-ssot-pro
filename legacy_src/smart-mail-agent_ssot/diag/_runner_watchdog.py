import os, sys, faulthandler, time, runpy, signal
# 超時後自動傾印所有執行緒堆疊
timeout = int(os.environ.get("SMA_FAULT_TIMEOUT", "60"))
faulthandler.dump_tracebacks_later(timeout, repeat=False, file=open("diag/faulthandler_stacks.txt","w"))
try:
    # 直接當成 -m smart_mail_agent.cli.e2e 執行
    sys.argv = ["-m","smart_mail_agent.cli.e2e", os.environ.get("SMA_EML_DIR","data/demo_eml")]
    runpy.run_module("smart_mail_agent.cli.e2e", run_name="__main__")
finally:
    faulthandler.cancel_dump_tracebacks_later()
