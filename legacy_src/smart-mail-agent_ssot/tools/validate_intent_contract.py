from __future__ import annotations
import sys, json, re
from pathlib import Path

contract_path = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts_prod/intent_contract.json")
names_path    = Path("artifacts_prod/intent_names.json")

data = json.loads(contract_path.read_text(encoding="utf-8"))
names = json.loads(names_path.read_text(encoding="utf-8")).get("names", [])

errors = []

if not isinstance(data, dict):
    errors.append("contract must be an object")

ints = data.get("intents")
if not isinstance(ints, list) or not ints:
    errors.append("'intents' must be a non-empty list")
else:
    seen = set()
    for i, it in enumerate(ints):
        if not isinstance(it, dict):
            errors.append(f"intents[{i}] must be an object"); continue
        name = it.get("name")
        subj = it.get("subject_tag")
        atts = it.get("attachments")
        inline = it.get("inline")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"intents[{i}].name must be non-empty string")
        if not isinstance(atts, list):
            errors.append(f"intents[{i}].attachments must be list")
        if inline is not None and not isinstance(inline, (str, type(None))):
            errors.append(f"intents[{i}].inline must be null or string")
        if not isinstance(subj, str) or not re.fullmatch(r"\[.+\]", subj or ""):
            errors.append(f"intents[{i}].subject_tag must look like [名稱], got: {subj!r}")
        if isinstance(name, str) and isinstance(subj, str) and subj != f"[{name}]":
            errors.append(f"intents[{i}].subject_tag mismatch: expected [{name}] got {subj}")
        if name in seen:
            errors.append(f"duplicate intent name: {name}")
        seen.add(name)

# 與 names.json 對齊（集合相等）
if isinstance(ints, list):
    contract_names = [it.get("name") for it in ints if isinstance(it, dict)]
    if set(contract_names) != set(names):
        errors.append(f"names.json mismatch: contract={sorted(contract_names)} vs names.json={sorted(names)}")

if errors:
    print("[INVALID] intent_contract.json")
    for e in errors:
        print(" -", e)
    sys.exit(1)

print(f"[VALID] intent_contract.json OK :: {len(ints)} intents")
