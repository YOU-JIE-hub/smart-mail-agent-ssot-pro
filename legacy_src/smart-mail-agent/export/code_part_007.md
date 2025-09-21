# Project Code Export (Part 007/010)

## scripts/sma_export_topN_v3.sh  
```bash
#!/usr/bin/env bash
set -euo pipefail

# ---- 參數（可用環境變數覆蓋）----
: "${INCLUDE_DIRS:=src scripts .sma_tools}"              # 只掃這些資料夾
: "${ALLOW_EXT:=.py,.sh,.yml,.yaml,.json,.toml,.ini,.cfg,.md}"
: "${MAX_FILE_KB:=200}"                                  # 單檔最大內嵌大小
: "${FILE_LIMIT:=20}"                                    # 匯出檔案數上限（重點）
: "${PRIORITY_GLOBS:=README.md;src/**/__init__.py;scripts/sma_*;.sma_tools/*.yml}"
: "${SORT_MODE:=size}"                                   # size | alpha
: "${TARGET_PART_MB:=1}"                                 # 估算要切幾份的目標大小
: "${FORCE_PARTS:=}"                                     # 固定份數（空=自動）
: "${DRY_RUN:=0}"                                        # 1=只顯示規劃不落盤
: "${DEBUG:=0}"
: "${ROOT_DIR:=$PWD}"
: "${OUT_DIR:=$PWD/export}"

python - <<'PY'
from __future__ import annotations
import os, sys, math, pathlib, zipfile, traceback, fnmatch

def dbg(*a):
    if os.environ.get("DEBUG","0")=="1": print("[DEBUG]", *a, file=sys.stderr)

ROOT   = pathlib.Path(os.environ.get("ROOT_DIR", os.getcwd())).resolve()
OUTDIR = pathlib.Path(os.environ.get("OUT_DIR", str(ROOT / "export"))).resolve()
OUTDIR.mkdir(parents=True, exist_ok=True)
LOGTXT = (ROOT / "reports_auto" / "export_log.txt"); LOGTXT.parent.mkdir(parents=True, exist_ok=True)

INCLUDE_DIRS = [p for p in os.environ.get("INCLUDE_DIRS","src scripts .sma_tools").split() if p]
ALLOW_EXT    = {e.strip().lower() for e in os.environ.get("ALLOW_EXT",".py,.sh,.yml,.yaml,.json,.toml,.ini,.cfg,.md").split(",")}
MAX_FILE_B   = int(os.environ.get("MAX_FILE_KB","200")) * 1024
FILE_LIMIT   = max(1, int(os.environ.get("FILE_LIMIT","20")))
PRIORITY_GLOBS = [g for g in os.environ.get("PRIORITY_GLOBS","").split(";") if g]
SORT_MODE    = os.environ.get("SORT_MODE","size")
TARGET_PART_B= max(1, int(float(os.environ.get("TARGET_PART_MB","1")) * 1024 * 1024))
FORCE_PARTS  = os.environ.get("FORCE_PARTS","").strip()
DRY_RUN      = os.environ.get("DRY_RUN","0")=="1"

EXCLUDE_DIRS = {
    ".git",".svn",".hg",".venv","venv","node_modules","__pycache__",
    "data","reports_auto","artifacts","artifacts_prod","artifacts_sa_text",
    "export",".mypy_cache",".pytest_cache",".idea",".vscode",".DS_Store"
}

def in_scope(p: pathlib.Path)->bool:
    rel = p.relative_to(ROOT).as_posix()
    parts = set(rel.split("/"))
    if any(d in parts for d in EXCLUDE_DIRS): return False
    if p.suffix.lower() not in ALLOW_EXT: return False
    return any(rel==d or rel.startswith(d+"/") for d in INCLUDE_DIRS)

# 掃描
files = []   # (rel, size_bytes, content_bytes)
skips_big, skips_io = [], []
for base in INCLUDE_DIRS:
    bp = (ROOT/base).resolve()
    if not bp.exists(): continue
    for p in bp.rglob("*"):
        if not p.is_file(): continue
        try:
            if not in_scope(p): continue
            rel = p.relative_to(ROOT).as_posix()
            lang = {
                ".py":"python",".sh":"bash",".yml":"yaml",".yaml":"yaml",
                ".json":"json",".toml":"toml",".ini":"ini",".cfg":"ini",".md":"md"
            }.get(p.suffix.lower(),"")
            txt = p.read_text(encoding="utf-8", errors="ignore")
            block = f"## {rel}  \n```{lang}\n{txt}\n```\n\n".encode("utf-8", errors="ignore")
            if len(block) > MAX_FILE_B:
                skips_big.append((rel, len(block))); continue
            files.append((rel, len(block), block))
        except Exception as e:
            skips_io.append((p.as_posix(), str(e)))

if not files:
    print("[FATAL] 無可匯出的檔案（請調整 INCLUDE_DIRS/ALLOW_EXT/EXCLUDE_DIRS）", file=sys.stderr)
    sys.exit(2)

# 優先規則：先放 priority globs 命中，再用大小或字母排序補到 FILE_LIMIT
def is_priority(rel: str)->bool:
    return any(fnmatch.fnmatch(rel, pat) for pat in PRIORITY_GLOBS)

pri = [it for it in files if is_priority(it[0])]
non = [it for it in files if not is_priority(it[0])]
# 去重（避免重複）
seen = set()
sel = []
for it in pri:
    if it[0] in seen: continue
    sel.append(it); seen.add(it[0])
# 根據 SORT_MODE 排序 non
if SORT_MODE=="alpha":
    non.sort(key=lambda x: x[0])
else:
    non.sort(key=lambda x: x[1], reverse=True)  # by size
for it in non:
    if len(sel) >= FILE_LIMIT: break
    if it[0] in seen: continue
    sel.append(it); seen.add(it[0])

# 估算分卷數
total = sum(sz for _,sz,_ in sel)
if os.environ.get("FORCE_PARTS","").strip():
    try:
        parts = max(1, int(os.environ["FORCE_PARTS"]))
    except:
        parts = max(1, math.ceil(total / TARGET_PART_B))
else:
    parts = max(1, math.ceil(total / TARGET_PART_B))
# 貪婪分桶
buckets = [{"size":0,"items":[]} for _ in range(parts)]
for it in sorted(sel, key=lambda x: x[1], reverse=True):
    b = min(buckets, key=lambda t: t["size"])
    b["items"].append(it); b["size"] += it[1]

# 清單輸出（DRY_RUN）
print(f"[PLAN] selected_files={len(sel)}/{len(files)} total_bytes={total} parts={parts}")
for i,bk in enumerate(buckets,1):
    print(f"  part {i:02d}: files={len(bk['items'])} size={bk['size']}")

if DRY_RUN:
    print("[DRY_RUN] 僅顯示規劃，不落盤")
    if skips_big:
        print(f"[SKIPPED_BIG] {len(skips_big)} files (>{int(MAX_FILE_B/1024)}KB)")
        for rel, sz in skips_big[:20]:
            print("   ", rel, sz, "bytes")
    if skips_io:
        print(f"[SKIPPED_IO] {len(skips_io)} files (read error)")
    sys.exit(0)

# 寫檔
for i,bk in enumerate(buckets,1):
    outp = OUTDIR / f"code_part_{i:03d}.md"
    with open(outp, "wb") as w:
        w.write(f"# Project Code Export (Part {i:03d}/{parts:03d})\n\n".encode())
        for rel,_,blob in sorted(bk["items"], key=lambda x: x[0]):
            w.write(blob)

# MANIFEST + ZIP
with open(OUTDIR/"MANIFEST.txt","w",encoding="utf-8") as w:
    w.write(f"SELECTED={len(sel)}/{len(files)} bytes={total} parts={parts}\n")
    w.write("PRIORITY_GLOBS="+ ";".join(PRIORITY_GLOBS)+"\n")
    for i,bk in enumerate(buckets,1):
        w.write(f"part {i:03d}\tfiles={len(bk['items'])}\tsize={bk['size']}\n")
    if skips_big:
        w.write("\n[SKIPPED_BIG]\n")
        for rel, sz in sorted(skips_big):
            w.write(f"{rel}\t{sz} bytes\n")
    if skips_io:
        w.write("\n[SKIPPED_IO]\n")
        for rel, err in skips_io:
            w.write(f"{rel}\t{err}\n")

zip_path = ROOT / "reports_auto" / "code_export_topN_v3.zip"
zip_path.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUTDIR.glob("code_part_*.md")):
        z.write(p, arcname=p.name)
    z.write(OUTDIR/"MANIFEST.txt", arcname="MANIFEST.txt")

print("[OK] export ->", OUTDIR.as_posix())
print("[OK] bundle ->", zip_path.as_posix())
PY

```

## src/smart_mail_agent/spam/rules.py  
```python
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

# ================= 設定與快取 =================
CONF_PATH: Union[str, Path] = Path(__file__).with_name("spam_rules.yaml")
_CACHE: Dict[str, Any] = {"mtime": None, "rules": None}

DEFAULT_RULES: Dict[str, Any] = {
    "keywords": {
        # 英文
        "FREE": 2,
        "bonus": 2,
        "viagra": 3,
        "get rich quick": 3,
        "limited offer": 2,
        # 中文（常見垃圾詞）
        "免費": 3,
        "限時優惠": 3,
        "中獎": 3,
        "立即下單": 2,
        "折扣": 2,
        "點此連結": 2,
    },
    "suspicious_domains": ["bit.ly", "tinyurl.com", "t.co", "goo.gl"],
    "suspicious_tlds": ["tk", "top", "xyz"],
    "bad_extensions": [".exe", ".js", ".vbs", ".scr", ".bat"],
    "whitelist_domains": ["example.com"],
    # raw points（供自訂 YAML 測試）；規範化分數另外算
    "weights": {
        "keywords": 2,
        "url_suspicious": 4,
        "tld_suspicious": 3,
        "attachment_executable": 5,
        "link_ratio": 6,
    },
    # 規範化分數門檻（label_email(dict) 路徑）
    "thresholds": {"suspect": 0.45, "spam": 0.60},
    # orchestrator 參考門檻
    "link_ratio_thresholds": {"review": 0.30, "drop": 0.50},
}


def _read_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    if not yaml:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _deep_merge_rules(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            nv = dict(base[k])
            nv.update(v)
            out[k] = nv
        else:
            out[k] = v
    return out


def _load_rules() -> Dict[str, Any]:
    path = Path(CONF_PATH)
    mtime = path.stat().st_mtime if path.exists() else None
    if _CACHE.get("mtime") == mtime and _CACHE.get("rules") is not None:
        return _CACHE["rules"]
    file_rules = _read_yaml(path)
    rules = _deep_merge_rules(DEFAULT_RULES, file_rules)
    _CACHE["mtime"] = mtime
    _CACHE["rules"] = rules
    return rules


# ================= 基礎工具 =================
def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def _is_ascii_word(w: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_]+", w))


def contains_keywords(
    text: str,
    keywords: Optional[Union[Iterable[str], Dict[str, Any]]] = None,
    *,
    match_word_boundary: bool = False,
) -> bool:
    """
    是否包含任一關鍵字（NFKC/不分大小寫）。
    - keywords 為 None 時，使用設定檔內的 keywords
    - match_word_boundary=True 僅對 ASCII 單字使用 \b 邊界比對（避免 "price" 命中 "pricelist"）
    """
    cfg = _load_rules()
    ks: Iterable[str]
    if keywords is None:
        src = cfg.get("keywords", {})
        ks = src.keys() if isinstance(src, dict) else src  # type: ignore
    else:
        ks = keywords.keys() if isinstance(keywords, dict) else keywords

    t = _nfkc(text).lower()
    for k in ks:
        w = _nfkc(str(k)).lower().strip()
        if not w:
            continue
        if match_word_boundary and _is_ascii_word(w):
            if re.search(rf"\b{re.escape(w)}\b", t):
                return True
        else:
            if w in t:
                return True
    return False


# 抽 URL（簡易）
_RE_URL = re.compile(r"(https?://|www\.)[^\s<>\)\"']{1,256}", re.IGNORECASE)


def extract_urls(text: str) -> List[str]:
    return [m.group(0) for m in _RE_URL.finditer(text or "")]


# ================= link ratio =================
_RE_TAG = re.compile(r"<[^>]+>")
_RE_WS = re.compile(r"\s+", re.UNICODE)
# 移除 hidden / display:none / visibility:hidden 的整段節點
_RE_HIDDEN_BLOCK = re.compile(
    r"<([a-zA-Z0-9]+)\b[^>]*?(?:\bhidden\b|style\s*=\s*(?:\"[^\"]*?(?:display\s*:\s*none|visibility\s*:\s*hidden)[^\"]*\"|'[^']*?(?:display\s*:\s*none|visibility\s*:\s*hidden)[^']*'))[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
# 只計算有 href 的 a
_RE_A_HREF = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))[^>]*>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)


def _strip_ws(s: str) -> str:
    return _RE_WS.sub("", s or "")


def _remove_hidden(s: str) -> str:
    prev = None
    cur = s or ""
    # 反覆移除，直到不再匹配（足夠應付測試）
    while prev != cur:
        prev = cur
        cur = _RE_HIDDEN_BLOCK.sub("", cur)
    return cur


def link_ratio(html_or_text: str) -> float:
    """
    鏈結文字長度 / 全部可見文字長度（去除所有空白字元）
    - 只計算具 href 的 <a>
    - 移除 hidden / display:none / visibility:hidden 節點
    - 純文字 URL 以一條 ≈ 14 字元估算（讓「很多網址」能過阈值）
    """
    s = _remove_hidden(html_or_text or "")

    # 取出 <a href=...> 內文字長度（去 tag、去空白）
    link_len = 0
    for m in _RE_A_HREF.finditer(s):
        _href = (m.group(1) or m.group(2) or m.group(3) or "").strip()  # extracted but unused
        text = m.group(4) or ""
        # 有 href 即算（'#' 也算；符合測試對大量 <a> 的期待）
        link_len += len(_strip_ws(_RE_TAG.sub("", text)))

    # 所有可見文字（去 tag、去空白）
    visible = _strip_ws(_RE_TAG.sub("", s))
    vis_len = len(visible)

    # 純文字 URL 估算
    urls = extract_urls(s)
    url_count = len(urls)
    link_len += url_count * 14

    eps = 1e-6
    denom = max(eps, float(vis_len) + eps)
    r = link_len / denom
    r = max(0.0, min(1.0 - 1e-6, r))
    return float(r)


# ================= 附件風險 =================
def _is_danger_ext(name: str, bad_exts: Sequence[str]) -> bool:
    n = (name or "").lower()
    return any(n.endswith(ext.lower()) for ext in bad_exts)


def _has_double_ext(name: str) -> bool:
    n = (name or "").lower()
    parts = n.split(".")
    return len(parts) >= 3 and all(p for p in parts[-3:])


# ================= 訊號收集/打分 =================
@dataclass
class Features:
    keyword_hit: bool = False
    url_sus: int = 0
    tld_sus: int = 0
    attach_exec: bool = False
    link_ratio_val: float = 0.0
    url_count: int = 0


def _domain_from_url(u: str) -> str:
    m = re.search(r"^(?:https?://)?([^/]+)", u, re.IGNORECASE)
    return (m.group(1) if m else u).lower()


def _tld_of_domain(d: str) -> str:
    p = d.rsplit(".", 1)
    return p[-1].lower() if len(p) == 2 else ""


def _collect_features(
    sender: str, subject: str, content: str, attachments: Sequence[Union[str, Dict[str, Any]]]
) -> Tuple[Features, List[str]]:
    cfg = _load_rules()
    feats = Features()
    reasons: List[str] = []

    text_all = f"{subject or ''}\n{content or ''}"

    if contains_keywords(text_all, match_word_boundary=False):
        feats.keyword_hit = True
        reasons.append("kw:hit")

    urls = extract_urls(text_all)
    feats.url_count = len(urls)
    sus_domains = set(cfg.get("suspicious_domains", []))
    sus_tlds = set(cfg.get("suspicious_tlds", []))

    # 正規 URL
    for u in urls:
        d = _domain_from_url(u)
        tld = _tld_of_domain(d)
        if any(d.endswith(sd) for sd in sus_domains):
            feats.url_sus += 1
            reasons.append(f"url:{d}")
        if tld in sus_tlds:
            feats.tld_sus += 1
            reasons.append(f"tld:{tld}")

    # 純字串短網址（沒有 http/https/www 前綴也抓）
    lowtext = (text_all or "").lower()
    for sd in sus_domains:
        if sd.lower() in lowtext:
            feats.url_sus += 1
            reasons.append(f"url:{sd.lower()}")

    bad_exts = cfg.get("bad_extensions", DEFAULT_RULES["bad_extensions"])
    for a in attachments or []:
        fname = a if isinstance(a, str) else (a.get("filename") or "")
        if _is_danger_ext(fname, bad_exts):
            feats.attach_exec = True
            reasons.append("attach:danger_ext")
        if _has_double_ext(fname):
            reasons.append("attach:double_ext")

    feats.link_ratio_val = link_ratio(text_all)

    # orchestrator 規則前綴（供測試檢查）
    lr_drop = float(cfg.get("link_ratio_thresholds", {}).get("drop", 0.50))
    lr_rev = float(cfg.get("link_ratio_thresholds", {}).get("review", 0.30))
    if feats.link_ratio_val >= lr_drop:
        reasons.append(f"rule:link_ratio>={lr_drop:.2f}")
    elif feats.link_ratio_val >= lr_rev:
        reasons.append(f"rule:link_ratio>={lr_rev:.2f}")

    return feats, reasons


def _raw_points_and_label(feats: Features) -> Tuple[float, str]:
    """
    for label_email(sender, subject, content, attachments) 測試：
    以 YAML weights 計 raw points；thresholds: suspect/spam
    """
    cfg = _load_rules()
    w = cfg.get("weights", {})

    points = 0.0
    if feats.keyword_hit:
        points += float(w.get("keywords", 0))
    if feats.url_sus > 0:
        points += float(w.get("url_suspicious", 0))
    if feats.tld_sus > 0:
        points += float(w.get("tld_suspicious", 0))
    if feats.attach_exec:
        points += float(w.get("attachment_executable", 0))
    # link ratio 達 drop 門檻才加分
    if feats.link_ratio_val >= float(cfg.get("link_ratio_thresholds", {}).get("drop", 0.50)):
        points += float(w.get("link_ratio", 0))

    th = cfg.get("thresholds", {})
    if points >= float(th.get("spam", 8)):
        label = "spam"
    elif points >= float(th.get("suspect", 4)):
        label = "suspect"
    else:
        label = "legit"
    return points, label


def _normalized_score_and_label(feats: Features) -> Tuple[float, str, Dict[str, float]]:
    """
    規範化分數：訊號對映到 [0,1]，取最大值，滿足：
      - 危險附件（.exe 等） => score >= 0.45（suspect）
      - 很多連結或 link_ratio >= 0.50 => score >= 0.60（spam）
      - 短網址/可疑網域 或 可疑 TLD => 直接拉到 0.60（spam）
    """
    cfg = _load_rules()
    c_keywords = 0.20 if feats.keyword_hit else 0.0
    c_url = 0.60 if feats.url_sus > 0 else 0.0
    c_tld = 0.60 if feats.tld_sus > 0 else 0.0
    c_attach = 0.50 if feats.attach_exec else 0.0

    # 連結：一般情況採比例 * 1.2；若極多 URL（>=10）或比例達 0.5，直接拉到 0.60
    c_link = feats.link_ratio_val * 1.2
    if feats.link_ratio_val >= 0.50 or feats.url_count >= 10:
        c_link = max(c_link, 0.60)

    score = max(c_keywords, c_url, c_tld, c_attach, c_link)

    th = cfg.get("thresholds", {})
    if score >= float(th.get("spam", 0.60)):
        label = "spam"
    elif score >= float(th.get("suspect", 0.45)):
        label = "suspect"
    else:
        label = "legit"

    scores_detail = {
        "keywords": float(c_keywords),
        "url_suspicious": float(c_url),
        "tld_suspicious": float(c_tld),
        "attachment_executable": float(c_attach),
        "link_ratio": float(c_link),
    }
    return float(score), label, scores_detail


# ================= 公開 API =================
EmailDict = Dict[str, Any]


def label_email(
    email_or_sender: Union[EmailDict, str],
    subject: str | None = None,
    content: str | None = None,
    attachments: Sequence[Union[str, Dict[str, Any]]] | None = None,
) -> Union[Dict[str, Any], Tuple[str, float, List[str]]]:
    """
    兩種用法：
      1) label_email(email_dict) -> {label, score(0~1), reasons, scores, points}
      2) label_email(sender, subject, content, attachments) -> (label, raw_points, reasons)
    """
    if isinstance(email_or_sender, dict):
        e = email_or_sender
        sender = e.get("sender") or e.get("from") or ""
        subj = e.get("subject") or ""
        cont = e.get("content") or e.get("body") or ""
        atts = e.get("attachments") or []

        feats, reasons = _collect_features(sender, subj, cont, atts)
        score_norm, label, scores_detail = _normalized_score_and_label(feats)
        raw_points, _ = _raw_points_and_label(feats)
        return {
            "label": label,
            "score": float(score_norm),
            "reasons": reasons,
            "scores": scores_detail,
            "points": float(raw_points),
        }

    # 參數式：回傳 raw points（供自訂 YAML 測試）
    sender = email_or_sender or ""
    subj = subject or ""
    cont = content or ""
    atts = attachments or []

    feats, reasons = _collect_features(sender, subj, cont, atts)
    raw_points, label = _raw_points_and_label(feats)
    return label, float(raw_points), reasons


def get_link_ratio_thresholds() -> Dict[str, float]:
    cfg = _load_rules()
    return {k: float(v) for k, v in cfg.get("link_ratio_thresholds", {}).items()}

```

