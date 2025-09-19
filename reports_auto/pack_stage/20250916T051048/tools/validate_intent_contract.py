from __future__ import annotations
import sys, json, re
from pathlib import Path
contract_path = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts_prod/intent_contract.json")
names = json.loads(Path("artifacts_prod/intent_names.json").read_text(encoding="utf-8")).get("names", [])
data = json.loads(contract_path.read_text(encoding="utf-8"))
errors = []
ints = data.get("intents")
if not isinstance(ints, list) or not ints: errors.append("'intents' must be a non-empty list")
else:
    seen=set()
    for i,it in enumerate(ints):
        if not isinstance(it,dict): errors.append(f"intents[{i}] must be object"); continue
        name=it.get("name"); subj=it.get("subject_tag"); atts=it.get("attachments"); inline=it.get("inline")
        if not isinstance(name,str) or not name.strip(): errors.append(f"intents[{i}].name must be non-empty string")
        if not isinstance(atts,list): errors.append(f"intents[{i}].attachments must be list")
        if inline is not None and not (inline is None or isinstance(inline,str)): errors.append(f"intents[{i}].inline must be null or string")
        if not isinstance(subj,str) or not re.fullmatch(r"\[.+\]", subj or ""): errors.append(f"intents[{i}].subject_tag must be like [名稱]")
        if name in seen: errors.append(f"duplicate intent: {name}")
        seen.add(name)
    miss=[n for n in names if n not in seen]
    if miss: errors.append(f"names not covered by contract: {miss}")
if errors:
    print("[INVALID] intent_contract.json"); [print(" -",e) for e in errors]; sys.exit(1)
print(f"[VALID] intent_contract.json OK :: {len(ints)} intents")
