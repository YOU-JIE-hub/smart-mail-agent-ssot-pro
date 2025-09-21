from __future__ import annotations
import argparse, json, math, re
from pathlib import Path
from typing import List, Tuple

HEADER_RE = re.compile(r'^(## +)(.+)$')  # 我們產的 Codebook 每個檔案是 "## <path>"

Segment = Tuple[str, str, int]  # (title, text, approx_bytes)

def read_text(p: Path)->str:
    return p.read_text(encoding="utf-8", errors="replace")

def split_segments(md: str) -> List[Segment]:
    """
    依據二級標題 '## <path>' 切成段，第一段視為前言/樹狀目錄。
    回傳 [(title, text, approx_bytes), ...]，title 為路徑或前言名稱。
    """
    lines = md.splitlines(keepends=True)
    segments: List[Segment] = []
    buf = []
    title = "_PREFACE_"
    for ln in lines:
        m = HEADER_RE.match(ln)
        if m:
            if buf:
                text = "".join(buf)
                segments.append((title, text, len(text.encode("utf-8"))))
                buf = []
            title = m.group(2).strip()
        buf.append(ln)
    if buf:
        text = "".join(buf)
        segments.append((title, text, len(text.encode("utf-8"))))
    return segments

def chunk_by_size(segments: List[Segment], max_bytes: int) -> List[List[Segment]]:
    """
    以段為最小單位湊檔，不跨段切，避免破壞 ``` 區塊。
    （舊邏輯；保留相容）
    """
    chunks: List[List[Segment]] = []
    cur: List[Segment] = []
    cur_size = 0
    for title, text, n in segments:
        if n > max_bytes and title != "_PREFACE_":
            if cur:
                chunks.append(cur); cur=[]; cur_size=0
            chunks.append([(title, text, n)])
            continue
        if cur_size + n > max_bytes and cur:
            chunks.append(cur)
            cur = [(title, text, n)]
            cur_size = n
        else:
            cur.append((title, text, n))
            cur_size += n
    if cur:
        chunks.append(cur)
    return chunks

def chunk_by_target(segments: List[Segment], target_bytes: int) -> List[List[Segment]]:
    """
    以「目標大小」打包，確保不跨段；_PREFACE_ 若本身超大允許超標放入第一包。
    其他單段若超過 target，單獨成檔（與舊邏輯一致）。
    """
    chunks: List[List[Segment]] = []
    cur: List[Segment] = []
    cur_size = 0
    for title, text, n in segments:
        if n > target_bytes and title != "_PREFACE_":
            if cur:
                chunks.append(cur); cur=[]; cur_size=0
            chunks.append([(title, text, n)])
            continue
        if cur and (cur_size + n > target_bytes):
            chunks.append(cur)
            cur = [(title, text, n)]
            cur_size = n
        else:
            cur.append((title, text, n))
            cur_size += n
    if cur:
        chunks.append(cur)
    return chunks

def merge_to_limit(chunks: List[List[Segment]], max_parts: int) -> List[List[Segment]]:
    """
    若分組數仍 > 上限，合併相鄰且合併後大小最小的一對，重複直到 ≤ 上限。
    保序、避免大幅失衡。
    """
    if max_parts <= 0:
        return chunks
    def chunk_size(c: List[Segment]) -> int:
        return sum(n for _,_,n in c)

    while len(chunks) > max_parts:
        # 計算相鄰兩組合併後的大小，找到最小者
        best_i = None
        best_sum = None
        for i in range(len(chunks)-1):
            s = chunk_size(chunks[i]) + chunk_size(chunks[i+1])
            if best_sum is None or s < best_sum:
                best_sum = s
                best_i = i
        # 合併 best_i 與 best_i+1
        i = best_i  # type: ignore
        merged = chunks[i] + chunks[i+1]
        chunks = chunks[:i] + [merged] + chunks[i+2:]
    return chunks

def write_chunks(src_md: Path, max_bytes: int | None, max_parts: int | None):
    ts = re.search(r'(\d{8}T\d{6})', src_md.name)
    ts = ts.group(1) if ts else "NO_TS"
    outdir = Path("bundles") / f"codebook_parts_{ts}"
    outdir.mkdir(parents=True, exist_ok=True)

    raw = read_text(src_md)
    segs = split_segments(raw)
    total_bytes = sum(n for _,_,n in segs)

    # 1) 決定分組策略
    if max_parts and max_parts > 0:
        # 以總量/上限估算目標大小；若也給了 max_bytes，取兩者的「較大者」
        target = math.ceil(total_bytes / max_parts)
        if max_bytes:
            target = max(target, max_bytes)
        chunks = chunk_by_target(segs, target)
        if len(chunks) > max_parts:
            chunks = merge_to_limit(chunks, max_parts)
        strategy = f"max_parts={max_parts}, target_bytes≈{target}"
    else:
        # 維持舊行為（以大小分檔）
        if not max_bytes:
            # 舊預設 8MB
            max_bytes = 8 * 1024 * 1024
        chunks = chunk_by_size(segs, max_bytes)
        strategy = f"max_bytes={max_bytes}"

    index_md = ["# CODEBOOK Parts Index",
                f"- Source: `{src_md}`",
                f"- Strategy: {strategy}",
                f"- Total segments: {len(segs)}",
                f"- Total parts: {len(chunks)}",
                ""]
    manifest = {
        "source": str(src_md),
        "strategy": strategy,
        "total_segments": len(segs),
        "total_bytes": total_bytes,
        "parts": []
    }
    if max_bytes: manifest["max_bytes"] = max_bytes  # type: ignore
    if max_parts: manifest["max_parts"] = max_parts  # type: ignore

    for i, group in enumerate(chunks, 1):
        body = []
        titles = []
        size_sum = 0
        for title, text, n in group:
            body.append(text)
            titles.append(title)
            size_sum += n
        part_name = f"PART_{i:03d}.md"
        part_path = outdir / part_name
        part_path.write_text("".join(body), encoding="utf-8")
        manifest["parts"].append({
            "file": str(part_path),
            "size_bytes": size_sum,
            "titles": titles
        })
        index_md.append(f"- [{part_name}]({part_name})  —  approx {size_sum/1024/1024:.2f} MB, {len(titles)} segments")

    (outdir / "INDEX.md").write_text("\n".join(index_md) + "\n", encoding="utf-8")
    (outdir / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return outdir, manifest

def main():
    ap = argparse.ArgumentParser(description="Split PROJECT_CODEBOOK_<TS>.md into parts, preserving file boundaries.")
    ap.add_argument("codebook_md", help="Path to PROJECT_CODEBOOK_<TS>.md")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--max-mb", type=float, help="Target size per part in MB (default: 8MB if neither --max-mb nor --max-bytes nor --max-parts given)")
    g.add_argument("--max-bytes", type=int, help="Target size per part in bytes (override)")
    ap.add_argument("--max-parts", type=int, help="Upper bound on number of output files (e.g., 20)")
    args = ap.parse_args()

    # 計算 max_bytes（若使用 max-parts 單獨也可為 None）
    max_bytes = None
    if args.max_bytes is not None:
        max_bytes = int(args.max_bytes)
    elif args.max_mb is not None:
        max_bytes = int(args.max_mb * 1024 * 1024)

    outdir, mani = write_chunks(Path(args.codebook_md), max_bytes, args.max_parts)
    print(json.dumps({
        "outdir": str(outdir),
        "parts_count": len(mani["parts"]),
        "parts": [{"file": p["file"], "MB": round(p["size_bytes"]/1024/1024, 2), "segments": len(p["titles"])} for p in mani["parts"]],
        "index": str(Path(outdir)/"INDEX.md"),
        "manifest": str(Path(outdir)/"MANIFEST.json"),
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
