from __future__ import annotations

import argparse

VERSION = "0.4.0"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="sma")
    p.add_argument("--version", action="store_true")
    ns = p.parse_args(argv)
    if ns.version:
        print(f"smart-mail-agent {VERSION}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
