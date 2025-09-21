#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/cli/e2e_safe.py
# 模組用途
#   安全執行 E2E：自動建立 sample_eml 與 out_root，注入 sys.argv 後執行 e2e；崩潰落檔。
from __future__ import annotations

import faulthandler
import json
import os
import platform
import runpy
import sys
import time
import traceback
from pathlib import Path


def _root() -> Path:
    env = os.environ.get("SMA_ROOT")
    return Path(env) if env else Path(__file__).resolve().parents[3]


def env_snapshot() -> dict:
    return {
        "OFFLINE": os.environ.get("OFFLINE", ""),
        "SMA_ROOT": os.environ.get("SMA_ROOT", ""),
        "SMA_EML_DIR": os.environ.get("SMA_EML_DIR", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
    }


def versions() -> dict:
    out = {
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "modules": {},
    }
    for m in ("joblib", "numpy", "scipy", "sklearn", "pandas", "yaml", "reportlab", "requests", "bs4", "PIL"):
        try:
            mod = __import__(m)
            out["modules"][m] = getattr(mod, "__version__", "n/a")
        except Exception as e:
            out["modules"][m] = f"ERROR: {type(e).__name__}: {e}"
    return out


def ensure_sample_eml() -> Path:
    root = _root()
    d = Path(os.environ.get("SMA_EML_DIR") or (root / "sample_eml"))
    d.mkdir(parents=True, exist_ok=True)
    f = d / "sample_1.eml"
    if not f.exists():
        f.write_text("Subject: hello\n\nthis is a sample eml for e2e.", encoding="utf-8")
    return d


def ensure_out_root() -> Path:
    root = _root()
    out_root = root / "reports_auto" / "e2e_mail"
    out_root.mkdir(parents=True, exist_ok=True)
    return out_root


def _crash_log_path(ts: str) -> Path:
    root = _root()
    log_dir = root / "reports_auto" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    faulthandler.enable(open(log_dir / f"FAULTHANDLER_{ts}.log", "w"))
    return log_dir / f"CRASH_{ts}.log"


def main() -> int:
    ts = time.strftime("%Y%m%dT%H%M%S")
    crash_log = _crash_log_path(ts)
    try:
        eml_dir = ensure_sample_eml()
        out_root = ensure_out_root()
        sys.argv = [
            "smart_mail_agent.cli.e2e",
            "--eml-dir",
            str(eml_dir),
            "--out-root",
            str(out_root),
        ]
        runpy.run_module("smart_mail_agent.cli.e2e", run_name="__main__")
        print(f"[SAFE] E2E finished. out_root={out_root}")
        return 0
    except SystemExit as e:
        code = int(getattr(e, "code", 1) or 0)
        with open(crash_log, "w", encoding="utf-8") as f:
            f.write("# CRASH REPORT (SystemExit)\n")
            f.write(json.dumps({"exit_code": code}, ensure_ascii=False, indent=2))
            f.write("\n\n## ENV\n")
            f.write(json.dumps(env_snapshot(), ensure_ascii=False, indent=2))
            f.write("\n\n## VERSIONS\n")
            f.write(json.dumps(versions(), ensure_ascii=False, indent=2))
        print(f"[SAFE] non-zero exit captured -> {crash_log}")
        return code
    except Exception:
        with open(crash_log, "w", encoding="utf-8") as f:
            f.write("# CRASH REPORT (Exception)\n")
            f.write("\n## ENV\n")
            f.write(json.dumps(env_snapshot(), ensure_ascii=False, indent=2))
            f.write("\n\n## VERSIONS\n")
            f.write(json.dumps(versions(), ensure_ascii=False, indent=2))
            f.write("\n\n## TRACEBACK\n")
            traceback.print_exc(file=f)
        print(f"[SAFE] crash captured -> {crash_log}")
        return 99


if __name__ == "__main__":
    sys.exit(main())
