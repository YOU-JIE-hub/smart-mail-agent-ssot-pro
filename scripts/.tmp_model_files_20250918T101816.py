import os, json, re
from pathlib import Path
ROOT=Path.cwd(); TS="20250918T101816"; STATUS=ROOT/"reports_auto/status"
STATUS.mkdir(parents=True, exist_ok=True)
# 掃描範圍（排除重型目錄）
EXC={".git",".venv","venv","node_modules","__pycache__",".cache","dist","build","release_staging","chatpack","artifacts_inbox","datasets","data","weights"}
def skip(p:Path)->bool:
  rel=p.relative_to(ROOT).as_posix() if p!=ROOT else ""
  return any(rel==e or rel.startswith(e+"/") for e in EXC)
# 模型關鍵模式（不假設一定存在；用於定位現狀）
PATTERNS={
 "intent":[r"(?i)models?/intent", r"(?i)intent.*(model|artifacts|threshold|metric|report|card)", r"(?i)intent_rules", r"(?i)registry\\.json"],
 "spam":[r"(?i)models?/spam", r"(?i)spam.*(model|artifact|threshold|metric|report|card)"],
 "kie":[r"(?i)models?/kie", r"(?i)kie.*(model|artifact|schema|metric|report|card|tokenizer|config)"]
}
# 我們也會找通用產物
COMMON=[r"(?i)reports_auto/.+/(metrics|report|RCA|ERR)", r"(?i)runs/\\d{8}T\\d{6}", r"(?i)ActionPlan\\.schema\\.json", r"(?i)ActionResult\\.schema\\.json", r"(?i)MODEL_CARD\\.md", r"(?i)training_meta\\.json", r"(?i)thresholds?\\.json", r"(?i)metrics\\.json", r"(?i)registry\\.json"]
files=[]
for dp, dn, fn in os.walk(ROOT):
  p=Path(dp);
  if skip(p): dn[:]=[]; continue
  for name in fn:
    f=p/name; rel=f.relative_to(ROOT).as_posix(); files.append(rel)
def match_any(path, patterns):
  return any(re.search(p, path) for p in patterns)
out={"root":str(ROOT),"ts":TS,"by_task":{"intent":[],"spam":[],"kie":[]},"common":[]}
for rel in sorted(files):
  if match_any(rel,PATTERNS["intent"]): out["by_task"]["intent"].append(rel)
  if match_any(rel,PATTERNS["spam"]):   out["by_task"]["spam"].append(rel)
  if match_any(rel,PATTERNS["kie"]):    out["by_task"]["kie"].append(rel)
  if match_any(rel,COMMON):             out["common"].append(rel)
# 缺漏檢查（每個 task 應有的關鍵檔）
REQUIRED=["registry.json","metrics.json","thresholds.json","MODEL_CARD.md","training_meta.json"]
gaps=[]
for t in ["intent","spam","kie"]:
  paths="\\n".join(out["by_task"][t])
  miss=[k for k in REQUIRED if not re.search(r"(?i)"+re.escape(k), paths)]
  gaps.append({"task":t,"missing":miss})
j=(STATUS/f"MODEL_FILES_{TS}.json"); j.write_text(json.dumps(out,ensure_ascii=False,indent=2),"utf-8")
# Markdown 輸出
md=[f"# Model Files @ {TS}",f"- root: {out[\"root\"]}",""]
for t in ["intent","spam","kie"]:
  md.append(f"## {t.upper()}"); md.extend([f"- `{p}`" for p in out["by_task"][t]] or ["- (none)"]); md.append("")
md.append("## COMMON"); md.extend([f"- `{p}`" for p in out["common"]] or ["- (none)"]); md.append("")
(STATUS/f"MODEL_FILES_{TS}.md").write_text("\\n".join(md),"utf-8")
(STATUS/f"MODEL_GAPS_{TS}.md").write_text("\\n".join(["# Gaps"]+[f"- {g[\"task\"]}: missing {g[\"missing\"] or []}" for g in gaps]),"utf-8")
print("[OK]", j.name)
