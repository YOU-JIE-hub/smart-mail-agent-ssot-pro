from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai_rpa import nlp as nlp_mod
from ai_rpa import scraper as scraper_mod
from ai_rpa.mailguard import detector as mailguard_detector
from ai_rpa.actions_router import plan as plan_actions
from ai_rpa.actions_executor import Executor

ALIASES = {"spamcheck":"mailguard"}

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="ai-rpa", description="AI+RPA Pipeline")
    p.add_argument("--input-path", dest="input_path", default="", help="file or directory path")
    p.add_argument("--output", dest="output", default="", help="output json path")
    p.add_argument("--tasks", dest="tasks", default="", help="comma-separated tasks")
    p.add_argument("--url", dest="url", default="", help="optional URL for scraping")
    p.add_argument("--config", dest="config", default="", help="optional config path")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=False)
    p.add_argument("--allow-online", dest="allow_online", action="store_true", default=False)
    p.add_argument("--exec", dest="do_exec", action="store_true", default=False)
    return p.parse_known_args(argv)[0]

def _split_tasks(ts: str) -> List[str]:
    return [t.strip() for t in (ts or "").split(",") if t.strip()]

def _read_text(input_path: str) -> str:
    p = Path(input_path) if input_path else None
    if p and p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except Exception:
            return ""
    try:
        return sys.stdin.read()
    except Exception:
        return ""

def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv)
    tasks_raw = _split_tasks(args.tasks)
    tasks_exec = [ALIASES.get(t, t) for t in tasks_raw]
    out: Dict[str, Any] = {"ok": True, "artifacts": [], "tasks": tasks_raw, "unknown": [], "results": {}, "steps": [], "errors": []}

    text = _read_text(args.input_path)
    scraped: Optional[List[Dict[str, Any]]] = None

    for t_raw, t in zip(tasks_raw, tasks_exec):
        if t == "nlp":
            r = nlp_mod.analyze_text(text)
            out["results"]["nlp"] = r
            out["steps"].append("nlp:done")
        elif t == "scrape":
            scraped = scraper_mod.scrape(args.url or "")
            out["results"]["scrape"] = scraped
            out["steps"].append("scrape:done")
        elif t == "mailguard":
            verdict = mailguard_detector.detect(text, headers=None)
            out["results"]["spamcheck"] = verdict
            out["steps"].append("spamcheck:done")
        elif t == "actions":
            blocked = out.get("results", {}).get("spamcheck", {}).get("verdict") == "BLOCK"
            if blocked:
                out["steps"].append("actions:skipped_by_mailguard")
                # 不寫 results.actions
            else:
                steps = plan_actions(text, scraped=scraped)
                out["results"]["actions"] = steps
                out["steps"].append("actions:planned")
                if args.do_exec and steps:
                    outbox = Path(os.environ.get("SMA_OUTBOX", "outbox"))
                    workdir = Path(os.environ.get("SMA_WORKDIR", "workdir"))
                    dbpath = Path(os.environ.get("SMA_DB", "smart.sqlite"))
                    ex = Executor(workdir=workdir, outbox=outbox, db_path=dbpath, dry_run=False)
                    out["results"]["exec"] = ex.execute(steps, context={})
        else:
            out["unknown"].append(t_raw)
            out["errors"].append(f"unknown task: {t_raw}")

    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.stdout.flush()

    if args.output and not args.dry_run:
        try:
            Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            out["errors"].append(f"write output failed: {e}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
