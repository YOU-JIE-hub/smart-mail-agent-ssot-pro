from __future__ import annotations
from pathlib import Path
from typing import Iterable, Mapping, Any, Sequence, List, Iterator
import json

def dump_jsonl(records: Iterable[Mapping[str, Any]] | Sequence[Mapping[str, Any]],
               path: str | Path) -> str:
    """把多筆 dict 以 JSON Lines 寫入檔案；回傳檔案路徑字串。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(dict(rec), ensure_ascii=False) + "\n")
    return str(p)

def read_jsonl(path: str | Path) -> Iterator[dict]:
    """逐行讀取 JSON Lines，忽略空白/壞行；以產生器回傳。"""
    p = Path(path)
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue

def parse_jsonl(path: str | Path) -> List[dict]:
    """一次性讀取整個 JSON Lines；回傳 list[dict]。"""
    return list(read_jsonl(path))
