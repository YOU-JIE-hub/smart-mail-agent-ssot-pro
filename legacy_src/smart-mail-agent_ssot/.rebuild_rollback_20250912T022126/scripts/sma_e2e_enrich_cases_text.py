#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enrich latest E2E run's cases.jsonl with route-able text:
- Prefer original text/subject/body if already present
- Else try to read matching .eml (data/demo_eml or case['source_path'/'email_path'])
- Else synthesize a descriptive text from intent + fields.spans[].value
Outputs:
- Overwrites cases.jsonl (after backing up to cases.jsonl.bak_<ts>)
- Writes TEXT_ENRICH_SUMMARY.md in the run dir
- Errors to reports_auto/errors/TEXT_ENRICH_<ts>/error.log
"""
from pathlib import Path
import re, sys, json, time, traceback
from email import policy
from email.parser import BytesParser

ROOT = Path("/home/youjie/projects/smart-mail-agent_ssot").resolve()
TS = time.strftime("%Y%m%dT%H%M%S")
ERRDIR = ROOT / f"reports_auto/errors/TEXT_ENRICH_{TS}"
ERRDIR.mkdir(parents=True, exist_ok=True)

def elog(msg, exc=False):
    p = ERRDIR / "error.log"
    with p.open("a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%F %T')}] {msg}\n")
        if exc:
            f.write(traceback.format_exc() + "\n")

def list_e2e_dirs():
    base = ROOT / "reports_auto" / "e2e_mail"
    if not base.exists(): return []
    xs = [p for p in base.iterdir() if p.is_dir() and re.match(r"^\d{8}T\d{6}$", p.name)]
    xs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return xs

def choose_run(run_dir_arg: str):
    if run_dir_arg:
        p = Path(run_dir_arg)
        return p if p.is_absolute() else (ROOT / p)
    for d in list_e2e_dirs():
        if (d / "cases.jsonl").exists():
            return d
    return None

def eml_candidates(case: dict):
    hints = []
    for k in ("source_path","email_path","path","file"):
        v = case.get(k)
        if isinstance(v,str) and v.strip():
            hints.append(v)
    # also try by id convention: <id>.eml under data/demo_eml
    cid = case.get("case_id") or case.get("id")
    if isinstance(cid,str) and cid:
        hints.append(f"data/demo_eml/{cid}.eml")
        hints.append(f"data/eml/{cid}.eml")
    # general demo dirs
    hints.append("data/demo_eml")
    hints.append("data/eml")
    # de-dup
    seen = set(); out=[]
    for h in hints:
        if h not in seen:
            seen.add(h); out.append(h)
    return out

def read_eml(path_like) -> tuple[str,str]:
    p = Path(path_like)
    if p.is_dir():
        return ("","")  # not a file
    if not p.exists():
        return ("","")
    try:
        with p.open("rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)
        subj = msg.get("Subject","") or ""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype in ("text/plain","text/html"):
                    try:
                        body = part.get_content()
                    except Exception:
                        body = part.get_payload(decode=True) or b""
                        try: body = body.decode(part.get_content_charset() or "utf-8", "ignore")
                        except Exception: body = ""
                    break
        else:
            try:
                body = msg.get_content()
            except Exception:
                body = msg.get_payload(decode=True) or b""
                try: body = body.decode(msg.get_content_charset() or "utf-8", "ignore")
                except Exception: body = ""
        return (subj.strip(), (body or "").strip())
    except Exception:
        elog(f"read_eml failed: {p}", exc=True)
        return ("","")

def synthesize_text(case: dict) -> str:
    intent = case.get("intent") or case.get("pred_intent") or "其他"
    pieces = [f"意圖:{intent}"]
    fields = case.get("fields") or {}
    spans = fields.get("spans") or []
    # prefer explicit value if present
    vals = []
    for sp in spans:
        v = sp.get("value")
        if isinstance(v,str) and v.strip():
            vals.append(f"{sp.get('label','field')}={v}")
    if not vals and isinstance(fields, dict):
        for k,v in fields.items():
            if k=="spans": continue
            if isinstance(v,(str,int,float)) and f"{v}".strip():
                vals.append(f"{k}={v}")
    if vals:
        pieces.append("欄位:" + ", ".join(vals[:6]))
    else:
        pieces.append("內容:請求回覆與處理")
    # boost keywords to help rules
    kw = {
        "投訴":"退單 賠償 延遲 缺件 投訴 客訴 申訴",
        "報價":"報價 試算 折扣 採購 合約 SOW PO",
        "技術支援":"錯誤 無法 連線 500 502 bug error",
        "規則詢問":"SLA 條款 合約 規範 政策 policy FAQ 流程",
        "資料異動":"更改 變更 修改 更新 地址 電話 email 帳號 個資"
    }
    pieces.append("關鍵詞:" + kw.get(intent,"諮詢"))
    return "；".join(pieces)

def enrich_case(case: dict, demo_dirs_cache: list[Path]) -> tuple[dict,bool,str]:
    # if already has text-like fields, keep
    for k in ("text","subject","body","snippet","raw","html"):
        v = case.get(k)
        if isinstance(v,str) and v.strip():
            return (case, False, "kept")
    # try eml
    subj, body = "",""
    for hint in eml_candidates(case):
        p = Path(hint)
        if p.is_file():
            subj, body = read_eml(p)
            if subj or body: break
        elif p.is_dir():
            # try to pick first .eml for lack of better mapping
            try:
                emls = sorted([x for x in p.iterdir() if x.suffix.lower()==".eml"])
                if emls:
                    subj, body = read_eml(emls[0])
                    if subj or body: break
            except Exception:
                pass
    if subj or body:
        case["subject"] = subj
        case["body"] = body
        case["text"] = (subj+"\n"+body).strip()
        return (case, True, "from_eml")
    # synthesize
    case["text"] = synthesize_text(case)
    return (case, True, "synthetic")

def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default="")
    args = ap.parse_args(argv)

    run = choose_run(args.run_dir)
    if not run:
        print("[FATAL] no e2e run dir with cases.jsonl"); return 2
    cj = run/"cases.jsonl"
    raw = cj.read_text("utf-8", errors="ignore").splitlines()
    rows = [ln for ln in raw if ln.strip()]
    if not rows:
        print(f"[FATAL] empty cases.jsonl: {run}"); return 2

    out = []
    n_keep=n_eml=n_syn=0
    for ln in rows:
        try:
            rec = json.loads(ln)
        except Exception:
            elog(f"json decode error: {ln[:180]}")
            continue
        rec2, changed, how = enrich_case(rec, [])
        out.append(rec2)
        if not changed: n_keep += 1
        elif how=="from_eml": n_eml += 1
        else: n_syn += 1

    # backup and write
    bak = run/f"cases.jsonl.bak_{TS}"
    bak.write_text("\n".join(rows)+"\n", encoding="utf-8")
    with (run/"cases.jsonl").open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False)+"\n")

    # summary
    (run/"TEXT_ENRICH_SUMMARY.md").write_text(
        "# Text Enrich Summary\n"
        f"- run_dir: {run.as_posix()}\n"
        f"- total: {len(rows)}\n"
        f"- kept: {n_keep}\n"
        f"- from_eml: {n_eml}\n"
        f"- synthetic: {n_syn}\n"
        f"- backup: {bak.name}\n", encoding="utf-8"
    )
    print(f"[OK] enriched -> {run.as_posix()}/cases.jsonl")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SystemExit:
        pass
    except Exception:
        elog("fatal", exc=True)
        print("[FATAL] enrich failed")
