#!/usr/bin/env bash
set -euo pipefail

echo "[STEP] repo sanity"
[[ -f src/smart_mail_agent/__init__.py ]] || { echo "[FATAL] not a valid repo"; exit 91; }
mkdir -p reports_auto data/intent data/spam

echo "[STEP] run Python auditor/fixer"
python - <<'PY'
from __future__ import annotations
import json, re, sys, os
from pathlib import Path
from collections import Counter, defaultdict

ROOT=Path.cwd()
REPORT=Path("reports_auto/data_audit.md")
INTENT_TARGET=Path("data/intent/test_labeled.jsonl")
SPAM_GOLD=Path("data/spam/test_labeled.jsonl")
EXTERNAL_INFER=Path("data/intent/external_realistic_test.clean.jsonl")
ALIGNED_INFER=Path("data/spam/test_infer_aligned.jsonl")

REQ_INTENT_LABELS={"biz_quote","complaint","policy_qa","profile_update","tech_support","other"}

def list_jsonl():
    out=[]
    for p in ROOT.rglob("*.jsonl"):
        # 跳過明顯臨時或模型輸出
        if any(s in p.parts for s in ["reports_auto",".venv","artifacts","artifacts_prod","__pycache__"]): 
            continue
        out.append(p)
    return sorted(out)

def quick_scan(fp: Path, need_label_set: set[str] | None=None):
    n=0; ok=True; labels=Counter(); has_id=True
    try:
        with open(fp,encoding="utf-8",errors="ignore") as f:
            for i, line in enumerate(f,1):
                line=line.strip()
                if not line: continue
                try:
                    e=json.loads(line)
                except Exception:
                    ok=False; continue
                n+=1
                if "id" not in e: has_id=False
                if "label" in e:
                    labels[str(e["label"]).strip()]+=1
    except Exception as ex:
        ok=False
    score=0
    if n>0 and has_id:
        score+=1
    if need_label_set is not None and set(labels) and set(labels).issubset(need_label_set):
        score+=1
    return {"n":n,"ok":ok,"has_id":has_id,"labels":labels,"score":score}

def choose_intent_gold(cands:list[Path]):
    best=None; best_score=(-1,-1) # (score, n)
    for p in cands:
        s=quick_scan(p, REQ_INTENT_LABELS)
        if s["score"]>best_score[0] or (s["score"]==best_score[0] and s["n"]>best_score[1]):
            best=(p,s); best_score=(s["score"], s["n"])
    return best

def read_ids(fp: Path):
    ids=[]
    with open(fp,encoding="utf-8",errors="ignore") as f:
        for line in f:
            try:
                e=json.loads(line)
            except: 
                continue
            if "id" in e: ids.append(str(e["id"]))
    return ids

def build_aligned_infer(spam_gold_ids:set[str], search_roots:list[Path]) -> int:
    """在 data/** 裡找到能對齊 spam_gold 的樣本，組成一個推論輸入 JSONL。"""
    seen=set(); keep=[]
    for root in search_roots:
        for p in root.rglob("*.jsonl"):
            if any(x in p.parts for x in ["reports_auto","artifacts","artifacts_prod",".venv","__pycache__"]):
                continue
            with open(p,encoding="utf-8",errors="ignore") as f:
                for line in f:
                    try:
                        e=json.loads(line)
                    except: 
                        continue
                    _id=str(e.get("id",""))
                    if _id in spam_gold_ids and _id not in seen:
                        # 確保推論最少要 subject/body
                        keep.append({"id":_id,
                                     "subject":e.get("subject",""),
                                     "body":e.get("body",""),
                                     "attachments":e.get("attachments",[])})
                        seen.add(_id)
        if len(seen)==len(spam_gold_ids):
            break
    if keep:
        ALIGNED_INFER.parent.mkdir(parents=True, exist_ok=True)
        with open(ALIGNED_INFER,"w",encoding="utf-8") as w:
            for e in keep: w.write(json.dumps(e,ensure_ascii=False)+"\n")
    return len(keep)

# ---------- 1) 找 Intent gold ----------
all_jsonl=list_jsonl()
intent_candidates=[p for p in all_jsonl if re.search(r'intent.*(test|label)', str(p), re.I)]
if not intent_candidates:
    # 放寬搜尋：含 label 且類別落在需求集合
    for p in all_jsonl:
        s=quick_scan(p, REQ_INTENT_LABELS)
        if s["score"]>=2:
            intent_candidates.append(p)
intent_pick=None
intent_info=None
if intent_candidates:
    intent_pick,intent_info=choose_intent_gold(intent_candidates)
    if intent_pick:
        INTENT_TARGET.parent.mkdir(parents=True, exist_ok=True)
        if INTENT_TARGET.resolve()!=intent_pick.resolve():
            # 覆蓋到正規路徑
            with open(INTENT_TARGET,"w",encoding="utf-8") as w, open(intent_pick,encoding="utf-8",errors="ignore") as f:
                for line in f: w.write(line)
        print(f"[INTENT] gold -> {INTENT_TARGET} (src={intent_pick}) N={intent_info['n']} labels={dict(intent_info['labels'])}")
else:
    print("[INTENT] gold NOT found. You need data/intent/test_labeled.jsonl with labels:", sorted(REQ_INTENT_LABELS))

# ---------- 2) Spam 對齊檢查 ----------
spam_gold_n=spam_infer_n=inter_n=0
spam_gold_ids=set()
if SPAM_GOLD.exists():
    spam_gold_ids=set(read_ids(SPAM_GOLD))
    spam_gold_n=len(spam_gold_ids)
    print(f"[SPAM] gold = {SPAM_GOLD} | ids={spam_gold_n}")
else:
    print("[SPAM] gold NOT found at data/spam/test_labeled.jsonl")

if EXTERNAL_INFER.exists():
    infer_ids=set(read_ids(EXTERNAL_INFER))
    spam_infer_n=len(infer_ids)
    inter_n=len(spam_gold_ids & infer_ids) if spam_gold_ids else 0
    print(f"[SPAM] infer_input = {EXTERNAL_INFER} | ids={spam_infer_n} | intersect_with_gold={inter_n}")
else:
    print("[SPAM] external infer input NOT found at data/intent/external_realistic_test.clean.jsonl")

# 若不對齊，就試著在 data/** 內拼一份對齊 spam gold 的推論輸入
rebuilt=0
if spam_gold_ids:
    rebuilt=build_aligned_infer(spam_gold_ids, [Path("data")])
    if rebuilt:
        print(f"[SPAM] built aligned infer input -> {ALIGNED_INFER} | ids={rebuilt}")
    else:
        print("[SPAM] unable to rebuild aligned infer input from data/**")

# ---------- 3) 寫報告 ----------
lines=[]
lines.append("# Data Audit\n")
lines.append("## Intent\n")
if intent_pick:
    lines.append(f"- Gold: `{INTENT_TARGET}`  (from `{intent_pick}`)\n")
    lines.append(f"- N: **{intent_info['n']}**\n- Labels: `{sorted(intent_info['labels'])}`\n")
else:
    lines.append("- Gold: **MISSING** → expected at `data/intent/test_labeled.jsonl` with labels "
                 f"`{sorted(REQ_INTENT_LABELS)}`\n")

lines.append("\n## Spam\n")
if SPAM_GOLD.exists():
    lines.append(f"- Gold: `{SPAM_GOLD}`  | ids={spam_gold_n}\n")
else:
    lines.append("- Gold: **MISSING** at `data/spam/test_labeled.jsonl`\n")

if EXTERNAL_INFER.exists():
    lines.append(f"- Your previous infer input: `{EXTERNAL_INFER}` | ids={spam_infer_n}")
    lines.append(f"- Intersect ids with gold: **{inter_n}**")
    if inter_n==0:
        lines.append("  - ⚠️ ID sets do **NOT** align. This is why eval showed '沒有可對齊的 id'.")
else:
    lines.append("- Previous infer input: **MISSING** (`data/intent/external_realistic_test.clean.jsonl`)\n")

if rebuilt:
    lines.append(f"- Built aligned infer input: `{ALIGNED_INFER}` | ids={rebuilt}\n")
else:
    lines.append("- Built aligned infer input: **not available** (couldn't find matching IDs under `data/**`).\n")

REPORT.write_text("\n".join(lines), encoding="utf-8")
print(f"[WRITE] {REPORT}")
PY

echo
echo "==== SUMMARY ===="
[[ -f data/intent/test_labeled.jsonl ]] && echo "[OK] Intent gold ready: data/intent/test_labeled.jsonl" || echo "[MISS] Intent gold still missing."
[[ -f data/spam/test_labeled.jsonl ]] && echo "[OK] Spam gold: data/spam/test_labeled.jsonl" || echo "[MISS] Spam gold missing."
[[ -f data/spam/test_infer_aligned.jsonl ]] && echo "[OK] Built aligned spam infer input: data/spam/test_infer_aligned.jsonl" || echo "[INFO] No aligned infer input rebuilt."
echo "[NOTE] Full audit: reports_auto/data_audit.md"
