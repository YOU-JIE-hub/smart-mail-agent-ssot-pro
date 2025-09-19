#!/usr/bin/env python3
import sys, json, argparse
from pathlib import Path

def _split_objects(stream: str):
    out, buf, depth, ins, esc = [], [], 0, False, False
    for ch in stream:
        buf.append(ch)
        if ins:
            if esc: esc = False
            elif ch == '\\': esc = True
            elif ch == '"': ins = False
        else:
            if ch == '"': ins = True
            elif ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    out.append(''.join(buf).strip()); buf = []
    tail = ''.join(buf).strip()
    if tail:
        out.extend([t for t in tail.replace('}\\n{','}\n{').splitlines() if t.strip()])
    return out

def load_jsonl_safe(p: Path):
    rows=[]; bad=0
    txt = p.read_text(encoding="utf-8", errors="ignore")
    for i, ln in enumerate(txt.splitlines(), 1):
        s = ln.strip()
        if not s: continue
        try:
            rows.append(json.loads(s)); continue
        except json.JSONDecodeError:
            fixed = s.replace('}\\n{','}\n{').replace('}\r\n{','}\n{').replace('}{','}\n{')
            ok=False
            for part in fixed.splitlines():
                q = part.strip()
                if not q: continue
                try:
                    rows.append(json.loads(q)); ok=True
                except Exception:
                    pass
            if not ok:
                for part in _split_objects(s):
                    try:
                        rows.append(json.loads(part)); ok=True
                    except Exception:
                        pass
            if not ok:
                bad += 1
                sys.stderr.write(f"[WARN] skip invalid line={i}\n")
        except Exception as e:
            bad += 1
            sys.stderr.write(f"[WARN] {p} line={i} err={e}\n")
    return rows, bad

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate","normalize","stats"])
    ap.add_argument("-i","--input", type=Path, required=True)
    ap.add_argument("-o","--output", type=Path)
    a = ap.parse_args()
    if a.cmd == "validate":
        _, bad = load_jsonl_safe(a.input)
        print("[VALID]" if bad==0 else f"[INVALID] bad_lines={bad}", a.input)
        sys.exit(0 if bad==0 else 4)
    if a.cmd == "normalize":
        if not a.output: print("[FATAL] normalize 需要 --output", file=sys.stderr); sys.exit(2)
        rows, bad = load_jsonl_safe(a.input)
        with a.output.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[NORMALIZED] {a.input} -> {a.output}  kept={len(rows)} skipped={bad}")
        sys.exit(0)
    if a.cmd == "stats":
        rows, bad = load_jsonl_safe(a.input)
        print(f"[STATS] file={a.input} rows={len(rows)} skipped={bad}")
        sys.exit(0)

if __name__ == "__main__":
    main()
