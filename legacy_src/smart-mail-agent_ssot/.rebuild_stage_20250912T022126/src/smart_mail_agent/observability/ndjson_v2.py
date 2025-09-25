from __future__ import annotations
from pathlib import Path
import json, time, traceback
from contextlib import contextmanager

class NDJSONLogger:
    def __init__(self, path:str, default_run_ts:str|None=None):
        self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.default_run_ts=default_run_ts
    def write(self, **kw):
        kw.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        if self.default_run_ts and "run_ts" not in kw:
            kw["run_ts"]=self.default_run_ts
        with self.path.open("a", encoding="utf-8") as w:
            w.write(json.dumps(kw, ensure_ascii=False)+"\n")

class log_step:
    def __init__(self, logger:NDJSONLogger, action:str, idem:str|None=None, **meta):
        self.l=logger; self.action=action; self.idem=idem; self.meta=meta
    def __enter__(self):
        self.l.write(action=f"{self.action}_start", result="ok", idem=self.idem, **self.meta); return self
    def __exit__(self, exc_type, exc, tb):
        if exc:
            self.l.write(action=f"{self.action}_fail", result="fail", idem=self.idem,
                         err_type=getattr(exc, "__class__", type(exc)).__name__,
                         err_msg=str(exc), **self.meta)
            return False
        self.l.write(action=f"{self.action}_done", result="ok", idem=self.idem, **self.meta)
        return False
