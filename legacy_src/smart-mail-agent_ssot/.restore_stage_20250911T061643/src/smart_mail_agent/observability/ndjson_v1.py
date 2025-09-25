from __future__ import annotations
import json, time, os, pathlib, traceback
class NDJSONLogger:
    def __init__(self, path: str):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_ts = os.getenv("RUN_TS") or self.path.stem
    def write(self, **ev):
        base=dict(ts=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
                  run_ts=self.run_ts, kind=ev.pop("kind","runner"),
                  level=ev.pop("level","INFO"), idem=ev.pop("idem",None),
                  case_id=ev.pop("case_id",None), intent=ev.pop("intent",None),
                  action=ev.pop("action",None), duration_ms=ev.pop("duration_ms",None),
                  result=ev.pop("result",None), err_type=ev.pop("err_type",None),
                  err_msg=ev.pop("err_msg",None))
        base.update(ev)
        with self.path.open("a",encoding="utf-8") as w:
            w.write(json.dumps(base,ensure_ascii=False)+"\n")
    def write_exception(self, action:str, exc:BaseException):
        self.write(level="ERROR", action=action, result="error",
                   err_type=exc.__class__.__name__,
                   err_msg="; ".join(traceback.format_exception_only(type(exc), exc)).strip())
