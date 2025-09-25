from __future__ import annotations
import os, re, json, csv, argparse, hashlib
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

ROOTS_DEFAULT = [
    "/home/youjie/projects/smart-mail-agent",
    "/home/youjie/projects/smart-mail-agent_ssot",
    "/home/youjie/projects/smart-mail-agent-ssot-pro",
]

EXCL_DIR = {".git","venv",".venv","node_modules","dist","build","artifacts","artifacts_prod","artifacts_inbox","weights","models","__pycache__","logs","reports_auto/logs"}
DATA_EXTS = {".jsonl",".json",".csv",".tsv"}
SPAM_PAT  = re.compile(r"(spam|spam_eval|spamassassin|sa\b)", re.I)
# 你意圖標籤（多類）——允許有缺字，但至少 3 種中文類別
INTENT_LABELS_CANON = {"報價","投訴","技術支援","規則詢問","資料異動","其他"}
# 常見 spam 二類集合
SPAM_LABELS_KNOWN   = {"ham","spam","0","1","true","false"}

def iter_code_paths(roots):
    CODE_EXT = {".py",".ipynb",".sh",".md",".yml",".yaml",".toml",".cfg",".ini",".env"}
    for r in roots:
        r = Path(r)
        if not r.exists(): continue
        for p in r.rglob("*"):
            try:
                if p.is_dir():
                    if p.name in EXCL_DIR: 
                        continue
                else:
                    if p.suffix.lower() in CODE_EXT:
                        yield p
            except Exception:
                continue

def derive_paths_from_code(roots):
    # 從程式碼抓出 *.jsonl/tsv/csv 的字面路徑（含相對路徑）
    CAND=set()
    STR=re.compile(r'(?P<q>["\'])(.+?\.(?:jsonl|json|csv|tsv))(?P=q)')
    for p in iter_code_paths(roots):
        try:
            s = p.read_text(encoding="utf-8", errors="ignore")
            for m in STR.finditer(s):
                rel = m.group(2)
                if len(rel)>512: continue
                CAND.add((str(p), rel))
        except Exception:
            pass
    resolved=set()
    for src,rel in CAND:
        # 絕對路徑
        if rel.startswith("/"):
            if Path(rel).exists():
                resolved.add(rel); continue
        # 相對：以代碼檔所在位置與 repo 根推
        srcp = Path(src)
        cand1 = (srcp.parent/rel).resolve()
        cand2 = None
        # 嘗試三個 root 拼接
        for root in ROOTS_DEFAULT:
            cand2 = (Path(root)/rel).resolve()
            if cand2.exists():
                resolved.add(str(cand2)); break
        if cand1.exists():
            resolved.add(str(cand1))
    return sorted(resolved)

def walk_data_files(roots):
    for r in roots:
        r = Path(r)
        if not r.exists(): continue
        for p in r.rglob("*"):
            try:
                if p.is_dir():
                    if p.name in EXCL_DIR: 
                        continue
                else:
                    if p.suffix.lower() in DATA_EXTS:
                        yield p
            except Exception:
                continue

def sample_reader(p:Path, limit:int=200000):
    # 支援 jsonl/json/tsv/csv，試抓 label/intent/category 欄位
    n=0; labels=[]
    label_keys=("label","intent","category","y","target")
    try:
        ext=p.suffix.lower()
        if ext==".jsonl":
            import json
            with p.open("r",encoding="utf-8",errors="ignore") as f:
                for i,line in enumerate(f):
                    line=line.strip()
                    if not line: continue
                    n+=1
                    try:
                        j=json.loads(line)
                        for k in label_keys:
                            if k in j:
                                labels.append(str(j[k]))
                                break
                    except Exception:
                        pass
                    if n>=limit: break
        elif ext==".json":
            # 盡量不整檔 load；先掃頭 20 萬行找 "label":
            hit=0
            with p.open("r",encoding="utf-8",errors="ignore") as f:
                for i,line in enumerate(f):
                    if '"label"' in line or '"intent"' in line or '"category"' in line:
                        hit+=1
                    if i>200000: break
            # 如果疑似 JSONL，就當 JSONL 讀
            if hit>10:
                return sample_reader(p.with_suffix(".jsonl") if False else p, limit)
            # 否則小檔才整檔 parse
            if p.stat().st_size <= 50*1024*1024:
                import json
                obj=json.load(open(p,"r",encoding="utf-8"))
                if isinstance(obj,list):
                    for j in obj[:limit]:
                        if isinstance(j,dict):
                            for k in label_keys:
                                if k in j: labels.append(str(j[k])); break
                elif isinstance(obj,dict) and "data" in obj and isinstance(obj["data"],list):
                    for j in obj["data"][:limit]:
                        if isinstance(j,dict):
                            for k in label_keys:
                                if k in j: labels.append(str(j[k])); break
                n=len(labels)
        else:
            # tsv/csv
            sniffer=None
            with p.open("r",encoding="utf-8",errors="ignore") as f:
                head=f.readline()
                delim='\t' if p.suffix.lower()=='.tsv' or '\t' in head else ','
            with p.open("r",encoding="utf-8",errors="ignore") as f:
                rdr=csv.reader(f, delimiter=delim)
                header=None
                for i,row in enumerate(rdr):
                    if not row: continue
                    if header is None:
                        header=[c.strip().lower() for c in row]
                        # 找 label 欄
                        cand=[idx for idx,c in enumerate(header) if c in label_keys]
                        lab_idx=cand[0] if cand else (1 if len(row)>1 else 0)
                        header=("has", lab_idx)
                        continue
                    lab_idx=header[1]
                    if lab_idx<len(row):
                        labels.append(str(row[lab_idx]).strip())
                        n+=1
                    if n>=limit: break
        return n, labels
    except Exception:
        return 0, []

def classify_dataset(path:Path, n:int, labels:list[str]):
    # 嚴格規則：intent 必須 >=3 類 且 path 不含 spam；spam 僅 2 類且集合屬於已知二類或近似
    lab_cnt = Counter([str(x).strip() for x in labels if str(x).strip()!=""])
    uniq=set(lab_cnt.keys())
    uniq_low={x.lower() for x in uniq}
    has_zh = sum(1 for x in uniq if re.search(r'[\u4e00-\u9fff]', x))
    is_spam_name = bool(SPAM_PAT.search(str(path)))
    # spam 判斷
    spamish = (len(uniq_low)<=3) and (uniq_low <= {"ham","spam","0","1","true","false"})
    # intent 判斷
    intentish = (len(uniq)>=3) and (not is_spam_name) and (has_zh>=1)
    # 額外加分：和典型意圖標籤交集
    intersect_zh = len(uniq & INTENT_LABELS_CANON)
    return {
        "lab_counts": lab_cnt,
        "uniq": list(uniq),
        "uniq_n": len(uniq),
        "has_zh": has_zh,
        "is_spam_name": is_spam_name,
        "spamish": spamish,
        "intentish": intentish,
        "intent_intersect": intersect_zh
    }

def score_intent(meta):
    if not meta["intentish"]: return -1
    s  = 5
    s += min(5, meta["uniq_n"])          # 類別越多越好
    s += 3*min(2, meta["intent_intersect"])
    s += 1 if meta["has_zh"]>0 else 0
    s -= 4 if meta["is_spam_name"] else 0
    return s

def score_spam(meta):
    if not meta["spamish"]: return -1
    s  = 5
    s += (2 if meta["is_spam_name"] else 0)
    s += (1 if meta["uniq_n"]==2 else 0)
    return s

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", default=ROOTS_DEFAULT)
    ap.add_argument("--max", type=int, default=50, help="top-N to keep for each type")
    ap.add_argument("--limit", type=int, default=200000, help="rows to sample per file")
    args=ap.parse_args()

    roots=[Path(r) for r in args.roots]
    OUT = Path(f"reports_auto/refind_{datetime.now().strftime('%Y%m%dT%H%M%S')}")
    OUT.mkdir(parents=True, exist_ok=True)

    # 1) 從程式碼蒐集 path 候選
    code_paths = derive_paths_from_code(roots)

    # 2) 扫檔案 + 加上 code 候選
    seen=set()
    candidates=[]
    walk_list=list(walk_data_files(roots))
    for p in walk_list + [Path(x) for x in code_paths]:
        p = Path(p)
        if not p.exists(): continue
        if p.suffix.lower() not in DATA_EXTS: continue
        rp=str(p.resolve())
        if rp in seen: continue
        seen.add(rp)
        n, labels = sample_reader(p, limit=args.limit)
        if n==0: continue
        meta = classify_dataset(p, n, labels)
        item = {
            "path": rp,
            "size_bytes": p.stat().st_size,
            "n_scanned": n,
            "labels_top": dict(Counter(labels).most_common(10)),
            **meta
        }
        candidates.append(item)

    # 3) 各自打分 & 排序
    intents=[c for c in candidates if score_intent(c)>=0]
    spams  =[c for c in candidates if score_spam(c)>=0]
    intents.sort(key=lambda x:(score_intent(x), x["n_scanned"], x["size_bytes"]), reverse=True)
    spams.sort(key=lambda x:(score_spam(x), x["n_scanned"], x["size_bytes"]), reverse=True)

    best_intent = intents[0] if intents else None
    best_spam   = spams[0]   if spams   else None

    out_all = {
        "roots": [str(r) for r in roots],
        "code_refs": code_paths,
        "intents": intents[:args.max],
        "spams": spams[:args.max],
        "picked": {"intent": best_intent, "spam": best_spam}
    }
    (OUT/"FINDINGS.json").write_text(json.dumps(out_all, ensure_ascii=False, indent=2), "utf-8")

    # 4) 輸出 ENV（若缺就留空，但仍寫檔）
    def _v(x): return x["path"] if x else ""
    env = f'INTENT_DATA="{_v(best_intent)}"\nSPAM_DATA="{_v(best_spam)}"\n'
    (OUT/"DATA_PATHS.strict.env").write_text(env, "utf-8")

    # 5) 人類可讀摘要（前 15 名）
    def lines(lst):
        L=[]
        for i,c in enumerate(lst[:15], start=1):
            L.append(f'{i:2d}. {c["path"]}\n    classes={c["uniq_n"]} zh={c["has_zh"]} spam_name={c["is_spam_name"]} intent∩={c["intent_intersect"]}\n    top_labels={list(c["labels_top"].items())[:5]}')
        return "\n".join(L) if L else "(none)"
    summary = [
        "# Refind (strict) summary",
        f"- OUT: {OUT}",
        f"- PICKED.intent: {best_intent['path'] if best_intent else '(none)'}",
        f"- PICKED.spam  : {best_spam['path'] if best_spam else '(none)'}",
        "\n## Top INTENT",
        lines(intents),
        "\n## Top SPAM",
        lines(spams),
        "\n## From code refs (raw)",
        *[f"- {x}" for x in code_paths[:50]]
    ]
    (OUT/"SUMMARY.txt").write_text("\n".join(summary), "utf-8")
    print("\n".join(summary))
