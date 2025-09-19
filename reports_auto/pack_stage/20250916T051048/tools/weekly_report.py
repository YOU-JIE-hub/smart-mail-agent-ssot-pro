
from __future__ import annotations
import sqlite3, time
from pathlib import Path

DB=Path("db/sma.sqlite")
OUT=Path("reports_auto/weekly"); OUT.mkdir(parents=True, exist_ok=True)
ts=time.strftime("%Y%m%d")
md=OUT/f"weekly_{ts}.md"

def fetch(q):
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
    rs=con.execute(q).fetchall(); con.close()
    return rs

hitl = fetch("SELECT * FROM v_hitl_rate ORDER BY day DESC LIMIT 14")
kie  = fetch("SELECT * FROM v_kie_quality ORDER BY day DESC LIMIT 14")
spam = fetch("SELECT * FROM v_spam_quality ORDER BY day DESC LIMIT 14")
ml   = fetch("SELECT day, top1, ROUND(AVG(margin),4) AS avg_margin, COUNT(*) AS n FROM v_ml_signals GROUP BY day, top1 ORDER BY day DESC, n DESC LIMIT 100")

with md.open("w", encoding="utf-8") as f:
    f.write(f"# Weekly Quality Report ({ts})\n\n")
    f.write("## HITL rate (14d)\n\n| day | total | hitl | rate |\n|---|---:|---:|---:|\n")
    for r in hitl:
        f.write(f"| {r['day']} | {r['total']} | {r['hitl']} | {r['rate']:.2f} |\n")

    f.write("\n## KIE quality (14d)\n\n| day | exact_micro | overlap_micro | exact_macro | overlap_macro |\n|---|---:|---:|---:|---:|\n")
    for r in kie:
        f.write(f"| {r['day']} | {r['exact_micro_f1']:.3f} | {r['overlap_micro_f1']:.3f} | {r['exact_macro_f1']:.3f} | {r['overlap_macro_f1']:.3f} |\n")

    f.write("\n## Spam quality (14d)\n\n| day | source | macro_f1 |\n|---|---|---:|\n")
    for r in spam:
        f.write(f"| {r['day']} | {r['source']} | {r['macro_f1']:.4f} |\n")

    f.write("\n## ML margin by top1 (avg)\n\n| day | top1 | avg_margin | n |\n|---|---|---:|---:|\n")
    for r in ml:
        f.write(f"| {r['day']} | {r['top1']} | {r['avg_margin']:.4f} | {r['n']} |\n")

print("[WEEKLY] wrote", md)
