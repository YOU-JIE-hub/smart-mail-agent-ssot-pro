#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, glob, os, re
from pathlib import Path

ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot")

cands=[]
for m in glob.glob(str(ROOT/"reports_auto/eval/*/metrics.json")):
    j=json.load(open(m,"r",encoding="utf-8"))
    if j.get("dataset_size",0)>1:
        cands.append(os.path.dirname(m))
cands.sort()
EVAL_DIR=cands[-1]

mj = json.load(open(Path(EVAL_DIR)/"metrics.json","r",encoding="utf-8"))
kie = mj.get("kie",{}).get("_micro",{})
tp, fn = kie.get("tp",0), kie.get("fn",0)

md_path = Path(EVAL_DIR)/"metrics.md"
txt = md_path.read_text(encoding="utf-8")

if tp==0 and fn==0:
    # 刪除 "## KIE" 段落
    txt = re.sub(r"\n## KIE[\s\S]*$", "\n## KIE\n- 無標註（略過評估）\n", txt)
    md_path.write_text(txt, encoding="utf-8")
    print("[OK] KIE section redacted due to no gold:", md_path)
else:
    print("[SKIP] KIE gold present; no redact.")
