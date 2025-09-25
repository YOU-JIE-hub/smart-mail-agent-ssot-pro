from __future__ import annotations

import argparse

from modules import run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--from_", dest="sender", required=True)
    args = ap.parse_args()
    print(run(args.subject, args.content, args.sender))


if __name__ == "__main__":
    main()
