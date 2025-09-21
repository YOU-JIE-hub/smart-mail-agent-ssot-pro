#!/usr/bin/env python3
import os, argparse, hashlib, sys

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

def parse_pointer(p):
    meta = {}
    with open(p, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith('#') or ':' not in line: continue
            k,v = line.split(':',1)
            meta[k.strip()] = v.strip()
    return meta

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, help='專案根目錄（含原始大檔）')
    ap.add_argument('--stage', required=True, help='handoff/<TS>/stage 路徑')
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    stage = os.path.abspath(args.stage)

    ok = fail = 0
    for dirpath, _, files in os.walk(stage):
        for fn in files:
            if not fn.endswith('.POINTER'): continue
            p = os.path.join(dirpath, fn)
            meta = parse_pointer(p)
            rel = meta.get('REL'); want = meta.get('SHA256')
            if not rel or not want:
                print(f"[BAD] {os.path.relpath(p, stage)}: 缺 REL/SHA256")
                fail += 1; continue
            target = os.path.join(root, rel)
            if not os.path.isfile(target):
                print(f"[MISS] {os.path.relpath(p, stage)}: 本機缺檔 {rel}")
                fail += 1; continue
            got = sha256(target)
            if got != want:
                print(f"[MISMATCH] {os.path.relpath(p, stage)}:\n  want {want}\n  got  {got}")
                fail += 1
            else:
                print(f"[OK] {rel}")
                ok += 1
    print(f"DONE pointers: ok={ok}, fail={fail}")
    sys.exit(1 if fail else 0)

if __name__ == '__main__':
    main()
