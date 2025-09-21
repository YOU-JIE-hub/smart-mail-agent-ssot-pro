#!/usr/bin/env python3
# 檔案位置：src/smart_mail_agent/spam/train/drift_report.py
# 模組用途：生成每週漂移報告（URL 主機、TLD、關鍵詞新詞）
from __future__ import annotations
import json, re
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any
from .features import load_rules, _url_hosts

def _read_jsonl(p: Path) -> list[dict]:
    out = []
    if not p.exists(): return out
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def drift_report(data_path: str, rules_path: str=".sma_tools/spam_rules.yml",
                 vocab_path: str="artifacts/spam_vocab.json", out_dir: str="reports_auto") -> None:
    rules = load_rules(rules_path) or {}
    data = _read_jsonl(Path(data_path))
    txts = [f"{x.get('subject','')}\n{x.get('body','')}" for x in data]
    hosts = []
    for t in txts: hosts.extend(_url_hosts(t))
    host_cnt = Counter(hosts).most_common(50)

    toks = re.findall(r'[A-Za-z\u4e00-\u9fa5]{2,}', "\n".join(txts))
    tok_cnt = Counter(t.lower() for t in toks).most_common(200)

    vocab_p = Path(vocab_path)
    base = {"hosts":{}, "tokens":{}}
    if vocab_p.exists():
        base = json.loads(vocab_p.read_text(encoding="utf-8"))
    else:
        vocab_p.parent.mkdir(parents=True, exist_ok=True)

    new_hosts = [h for h,_ in host_cnt if h not in base.get("hosts",{})]
    new_tokens = [t for t,_ in tok_cnt if t not in base.get("tokens",{})]

    # 更新基線（可選，這裡僅輸出不覆寫；你可在審核後再更新）
    out = {
        "top_hosts": host_cnt,
        "new_hosts": new_hosts,
        "top_tokens": tok_cnt,
        "new_tokens": new_tokens
    }
    out_dirp = Path(out_dir); out_dirp.mkdir(parents=True, exist_ok=True)
    ts = __import__("datetime").datetime.now().strftime("%Y%m%d")
    (out_dirp/f"spam_drift_{ts}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = []
    lines.append(f"[SPAM][DRIFT] Top hosts (50): {host_cnt[:10]} ...")
    lines.append(f"[SPAM][DRIFT] New hosts count: {len(new_hosts)}")
    lines.append(f"[SPAM][DRIFT] New tokens count: {len(new_tokens)}")
    (out_dirp/f"spam_drift_{ts}.txt").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="未標註或新批次 JSONL")
    ap.add_argument("--rules", default=".sma_tools/spam_rules.yml")
    ap.add_argument("--vocab", default="artifacts/spam_vocab.json")
    ap.add_argument("--out", default="reports_auto")
    args = ap.parse_args()
    drift_report(args.data, args.rules, args.vocab, args.out)
