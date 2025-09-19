#!/usr/bin/env python3
from __future__ import annotations

import faulthandler
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path


def ensure_sample_eml() -> Path:
    root = Path(os.environ.get("SMA_ROOT", Path(__file__).resolve().parents[3]))
    d = Path(os.environ.get("SMA_EML_DIR") or (root / "sample_eml"))
    d.mkdir(parents=True, exist_ok=True)
    f = d / "sample_1.eml"
    if not f.exists():
        f.write_text("Subject: hello\n\nthis is a sample eml.", encoding="utf-8")
    return d


def ensure_out_root() -> Path:
    root = Path(os.environ.get("SMA_ROOT", Path(__file__).resolve().parents[3]))
    out = Path(os.environ.get("SMA_OUT_ROOT") or (root / "reports_auto" / "e2e_mail"))
    out.mkdir(parents=True, exist_ok=True)
    return out


def _crash_log_path() -> Path:
    root = Path(os.environ.get("SMA_ROOT", Path.cwd()))
    log_dir = root / "reports_auto" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    return log_dir / f"CRASH_{ts}.log"


def main() -> int:
    faulthandler.enable()
    eml_dir = Path(os.environ.get("SMA_EML_DIR") or ensure_sample_eml())
    out_root = Path(os.environ.get("SMA_OUT_ROOT") or ensure_out_root())
    try:
        from smart_mail_agent.pipeline.run_action_handler import run_e2e_mail

        _ = run_e2e_mail(eml_dir, out_root)
        print(f"[SAFE] E2E finished. out_root={out_root}")
        return 0
    except SystemExit as e:
        p = _crash_log_path()
        with open(p, "w", encoding="utf-8") as f:
            f.write("# CRASH REPORT (SystemExit)\n")
            f.write(json.dumps({"exit_code": int(e.code or 1)}, ensure_ascii=False, indent=2))
        print(f"[SAFE] crash captured -> {p}")
        return int(e.code or 2)
    except Exception:
        p = _crash_log_path()
        with open(p, "w", encoding="utf-8") as f:
            f.write("# CRASH REPORT (Exception)\n")
            f.write("\n## ENV\n")
            f.write(json.dumps(dict(os.environ), ensure_ascii=False, indent=2))
            f.write("\n\n## VERSIONS\n")
            f.write(json.dumps({"python": sys.version, "platform": platform.platform()}, ensure_ascii=False, indent=2))
            f.write("\n\n## TRACEBACK\n")
            traceback.print_exc(file=f)
        print(f"[SAFE] crash captured -> {p}")
        return 99


if __name__ == "__main__":
    sys.exit(main())
