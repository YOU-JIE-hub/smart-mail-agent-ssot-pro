from __future__ import annotations
from pathlib import Path
import argparse, re, shutil, time

RUN_RE=re.compile(r"^\d{8}T\d{6}$")
def days_ago(n:int)->float: return time.time() - n*86400

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=90, help="保留最近 N 個 run")
    ap.add_argument("--ndjson_days", type=int, default=90)
    ap.add_argument("--eml_days", type=int, default=180)
    ap.add_argument("--root", default="reports_auto/e2e_mail")
    ap.add_argument("--evdir", default="reports_auto/events")
    ap.add_argument("--archive", default="archive")
    args=ap.parse_args()
    root,evdir,arch=Path(args.root),Path(args.evdir),Path(args.archive)
    arch.mkdir(parents=True, exist_ok=True)

    # 按 run 裁切
    runs=sorted([p for p in root.glob("*") if p.is_dir() and RUN_RE.match(p.name)])
    for p in runs[:-args.runs]:
        dest=arch/p.name
        if not dest.exists():
            shutil.move(str(p), str(dest))

    # NDJSON 舊檔移除
    cutoff=days_ago(args.ndjson_days)
    for p in evdir.glob("*.ndjson"):
        if p.stat().st_mtime < cutoff:
            p.unlink(missing_ok=True)

    # sent .eml 過舊壓縮封存（僅搬運，不刪 DB）
    cutoff_eml=days_ago(args.eml_days)
    for run in evdir.parent.parent.glob("e2e_mail/*"):
        sent=run/"rpa_out"/"email_sent"
        if not sent.exists(): continue
        for eml in sent.glob("*.eml"):
            if eml.stat().st_mtime < cutoff_eml:
                dest=arch/"sent_eml"/run.name; dest.mkdir(parents=True, exist_ok=True)
                shutil.move(str(eml), str(dest/eml.name))
    print("[OK] retention done")
if __name__=="__main__": main()
