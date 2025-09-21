from __future__ import annotations
import os, re, json
from pathlib import Path
ROOT=Path(".")
DISC=json.loads(os.popen("python tools/discover_intents_v3.py").read())
INTENTS=DISC.get("intents",[])
SEND=(ROOT/"tools"/"send_with_intent_attachments.py").read_text("utf-8",errors="ignore") if (ROOT/"tools"/"send_with_intent_attachments.py").exists() else ""

def guess_delivery(intent:str)->dict:
    t=SEND
    d={"subject_tag":None,"attachments":[],"inline":None}
    def hit(pat:str)->bool:
        try: return re.search(pat, t, re.I) is not None
        except re.error: return False
    if hit(fr"{intent}.*\.html|\.html.*{intent}|quote|報價"): d["attachments"].append("*.html")
    if hit(fr"{intent}.*\.json|\.json.*{intent}|diff|ticket|工單|差異"): d["attachments"].append("*.json")
    if hit(fr"FAQ|faq|知識庫"): d["inline"]="FAQ block"
    if hit(fr"ticket|工單"): d["subject_tag"]="[TICKET]"
    if not d["attachments"] and not d["inline"] and not d["subject_tag"]:
        d["unknown"]=True
    return d

contract={"version": os.getenv("TS",""), "intents":[{"name":it,"delivery":guess_delivery(it)} for it in INTENTS]}
Path("artifacts_prod").mkdir(parents=True, exist_ok=True)
Path(os.environ["CONTRACT"]).write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

lines=[
    "# Intent Contract (auto-generated)",
    f"- detected_counts: {json.dumps(DISC.get('counts',{}),ensure_ascii=False)}",
    f"- intents_detected: {len(INTENTS)}",
    "- names: " + (", ".join(INTENTS) if INTENTS else "(none)"),
    "",
    "## Delivery mapping"
]
for row in contract["intents"]:
    d=row["delivery"]; at=", ".join(d.get("attachments",[])) or "-"
    lines.append(f"- **{row['name']}** → attachments: {at}; inline: {d.get('inline','-')}; subject_tag: {d.get('subject_tag','-')}; {'⚠️ unknown' if d.get('unknown') else 'OK'}")
Path(os.environ["OUT_MD"]).parent.mkdir(parents=True, exist_ok=True)
Path(os.environ["OUT_MD"]).write_text("\n".join(lines), encoding="utf-8")
print("[OK] contract ->", os.environ["CONTRACT"])
print("[OK] report   ->", os.environ["OUT_MD"])
