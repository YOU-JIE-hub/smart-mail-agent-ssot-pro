#!/usr/bin/env python3
# 檔案位置: src/smart_mail_agent/__main__.py
"""
主進入點：轉呼叫現有專案的 src.run_action_handler 以維持相容。
"""

import subprocess
import sys


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = [sys.executable, "-m", "src.run_action_handler", *argv]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
