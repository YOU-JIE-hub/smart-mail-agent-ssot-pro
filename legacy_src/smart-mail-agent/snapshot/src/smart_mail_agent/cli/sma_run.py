#!/usr/bin/env python3
from __future__ import annotations

# 檔案位置: src/smart_mail_agent/cli/sma_run.py
import subprocess
import sys


def main() -> int:
    cmd = [sys.executable, "-m", "src.run_action_handler", *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
