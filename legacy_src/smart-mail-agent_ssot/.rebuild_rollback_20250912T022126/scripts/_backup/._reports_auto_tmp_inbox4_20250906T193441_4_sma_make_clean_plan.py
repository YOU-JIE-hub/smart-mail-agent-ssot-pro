#!/usr/bin/env python3
from __future__ import annotations
import json, time
from pathlib import Path

ROOT = Path("/home/youjie/projects/smart-mail-agent")
R = ROOT / "reports_auto" / "_refactor"
out_txt = R / "clean_plan.txt"
out_ndj = R / "clean_plan.ndjson"
R.mkdir(parents=True, exist_ok=True)

def load(name):
    p = R / name
    if not p.exists(): return []
    return json.loads(p.read_text(encoding="utf-8"))

entry = load("entry_conflicts.json")
same  = load("same_content.json")
diff  = load("diff_content.json")

def weight(path: str) -> int:
    if path.startswith("src/"): return 100
    if path.startswith("smart_mail_agent/") or path.startswith("ai_rpa/"): return 70
    if path.startswith("examples/legacy"): return 10
    return 40

def pick_winner(paths: list[str]) -> str:
    for p in paths:
        if "smart_mail_agent/routing/run_action_handler.py" in p: return p
    for p in paths:
        if "smart_mail_agent/cli/spamcheck.py" in p: return p
    return sorted(paths, key=lambda p: (-weight(p), -len(p)))[0]

lines=[]; stats={"DELETE_DUP":0,"ENTRY_KEEP":0,"ENTRY_REMOVE":0,"PREFER":0}
ts=time.strftime("%Y-%m-%d %H:%M:%S")
lines.append(f"# CLEAN PLAN @ {ts}")
lines += [
"# ACTION 說明：",
"# - DELETE_DUP <path>             # 同名同內容 → 可安全刪除",
"# - ENTRY_KEEP <winner> / ENTRY_REMOVE <loser>  # 入口衝突 → 僅留一份",
"# - PREFER <winner> <loser>       # 同名不同內容 → winner 為主，loser 進備份/合併工作區",
""
]

if entry:
    lines.append("## ENTRY CONFLICTS")
    for grp in entry:
        paths=[it["rel"] for it in grp["items"]]
        win=pick_winner(paths)
        lines.append(f"ENTRY_KEEP {win}"); stats["ENTRY_KEEP"]+=1
        for p in paths:
            if p!=win:
                lines.append(f"ENTRY_REMOVE {p}    # entry-conflict"); stats["ENTRY_REMOVE"]+=1
    lines.append("")

if same:
    lines.append("## DUPLICATES (SAFE TO DELETE)")
    for grp in same:
        paths=[it["rel"] for it in grp["items"]]
        win=pick_winner(paths)
        for p in paths:
            if p!=win:
                lines.append(f"DELETE_DUP {p}    # same-as {win}"); stats["DELETE_DUP"]+=1
    lines.append("")

if diff:
    lines.append("## DIFFERENT CONTENT (REQUIRES REVIEW)")
    for grp in diff:
        paths=[it["rel"] for it in grp["items"]]
        win=pick_winner(paths)
        for p in paths:
            if p!=win:
                lines.append(f"PREFER {win} {p}    # diff-same-name"); stats["PREFER"]+=1
    lines.append("")

lines.append("## STATS")
for k,v in stats.items(): lines.append(f"# {k}: {v}")

out_txt.write_text("\n".join(lines), encoding="utf-8")
with (out_ndj).open("w",encoding="utf-8") as f:
    for grp in entry:
        paths=[it["rel"] for it in grp["items"]]; win=pick_winner(paths)
        f.write(json.dumps({"action":"ENTRY_KEEP","path":win},ensure_ascii=False)+"\n")
        for p in paths:
            if p!=win: f.write(json.dumps({"action":"ENTRY_REMOVE","path":p,"reason":"entry-conflict"},ensure_ascii=False)+"\n")
    for grp in same:
        paths=[it["rel"] for it in grp["items"]]; win=pick_winner(paths)
        for p in paths:
            if p!=win: f.write(json.dumps({"action":"DELETE_DUP","path":p,"reason":f"same-as:{win}"},ensure_ascii=False)+"\n")
    for grp in diff:
        paths=[it["rel"] for it in grp["items"]]; win=pick_winner(paths)
        for p in paths:
            if p!=win: f.write(json.dumps({"action":"PREFER","winner":win,"loser":p,"reason":"diff-same-name"},ensure_ascii=False)+"\n")
print(f"SMA PRINT OK :: PLAN WRITTEN -> {out_txt} / {out_ndj}")
