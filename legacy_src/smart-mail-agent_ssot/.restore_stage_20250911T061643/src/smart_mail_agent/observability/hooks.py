from __future__ import annotations
import traceback

class log_step:
    def __init__(self, logger, action: str, idem: str|None=None, **kw):
        self.logger, self.action, self.idem, self.kw = logger, action, idem, kw
    def __enter__(self):
        self.logger.write(action=f"{self.action}_start", result="ok", idem=self.idem, **self.kw)
        return self
    def __exit__(self, exc_type, exc, tb):
        if exc:
            self.logger.write(
                action=f"{self.action}_fail", result="fail", idem=self.idem,
                err_type=getattr(exc, "__class__", type(exc)).__name__, err_msg=str(exc)
            )
            # 不吞例外，維持原本行為
            return False
        self.logger.write(action=f"{self.action}_done", result="ok", idem=self.idem, **self.kw)
        return False
