from __future__ import annotations

import argparse
import datetime
import sqlite3
from pathlib import Path

DB = Path("data/stats.db")


def init_stats_db() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS stats(
            id INTEGER PRIMARY KEY,
            ts TEXT,
            label TEXT,
            elapsed REAL
        )"""
        )


def increment_counter(label: str, elapsed: float) -> int:
    init_stats_db()
    with sqlite3.connect(DB) as c:
        cur = c.execute(
            "INSERT INTO stats(ts,label,elapsed) VALUES(?,?,?)",
            (datetime.datetime.utcnow().isoformat(), label, float(elapsed)),
        )
        return int(cur.lastrowid)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--label")
    ap.add_argument("--elapsed", type=float)
    ns = ap.parse_args(argv)
    if ns.init:  # type: ignore
        init_stats_db()
        print("資料庫初始化完成")
        return 0
    if ns.label and (ns.elapsed is not None):
        increment_counter(ns.label, ns.elapsed)
        print("已新增統計紀錄")
        return 0
    ap.print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
