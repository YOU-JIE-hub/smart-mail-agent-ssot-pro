import json, os, sys, pathlib, time
from collections import defaultdict

# 確保能匯入 scripts/hotfix/_io_utils.py
THIS = pathlib.Path(__file__).resolve()
SCRIPTS_DIR = THIS.parents[1]  # .../scripts
if SCRIPTS_DIR.as_posix() not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR.as_posix())

try:
    from hotfix._io_utils import safe_filename, build_minimal_eml, write_bytes, ensure_dir
except ModuleNotFoundError as e:
    # 最終保險：把 hotfix 目錄直接塞進 sys.path
    HOTFIX_DIR = THIS.parent
    if HOTFIX_DIR.as_posix() not in sys.path:
        sys.path.insert(0, HOTFIX_DIR.as_posix())
    from _io_utils import safe_filename, build_minimal_eml, write_bytes, ensure_dir  # type: ignore

BASE = THIS.parents[2]  # 專案根
ROOT = BASE / "reports_auto" / "e2e_mail"
LATEST = BASE / "reports_auto" / "e2e_mail" / "LATEST"
if not LATEST.exists():
    cands = [p for p in ROOT.glob("20*") if p.is_dir()]
    if cands:
        LATEST = sorted(cands)[-1]
    else:
        print("[ERR] no e2e outputs found", file=sys.stderr)
        sys.exit(2)

cases_path   = LATEST / "cases.jsonl"
actions_path = LATEST / "actions.jsonl"
outbox_dir   = LATEST / "rpa_out" / "email_outbox"
quar_dir     = LATEST / "rpa_out" / "quarantine"

ensure_dir(outbox_dir.as_posix())
ensure_dir(quar_dir.as_posix())

# 載入 cases 映射（供主旨/資訊使用）
cases = {}
if cases_path.exists():
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: 
                continue
            try:
                j = json.loads(line)
                cid = j.get("case_id") or j.get("id") or j.get("case") or j.get("cid")
                if cid:
                    cases[cid] = j
            except Exception:
                pass

patched = []
created = 0
with open(actions_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        try:
            a = json.loads(line)
        except Exception:
            patched.append(line)
            continue

        status = a.get("status")
        atype  = a.get("action_type") or a.get("action")
        cid    = a.get("case_id")
        intent = a.get("intent")

        # 只處理 SendEmail 的 downgraded（smtp_not_configured）
        if atype == "SendEmail" and (status == "downgraded" or a.get("error") == "smtp_not_configured"):
            # 原始 outbox 名稱 -> 安全檔名
            orig_path = a.get("outbox_path") or a.get("payload_ref") or ""
            base = os.path.basename(orig_path) if orig_path else f"{cid or 'mail'}_{int(time.time())}.eml"
            base = safe_filename(base)
            if not base.lower().endswith(".eml"):
                base += ".eml"
            final_path = outbox_dir / base

            if not final_path.exists():
                c = cases.get(cid or "")
                subj = (c or {}).get("subject") or (c or {}).get("title") or base.replace(".eml","")
                if not subj:
                    subj = base.replace(".eml","")

                # 附帶 quote 提示
                tips = []
                quotes_dir = LATEST / "rpa_out" / "quotes"
                if quotes_dir.exists():
                    for qf in quotes_dir.glob("*.html"):
                        if cid and cid in qf.name:
                            tips.append(f"- Quote: {qf.relative_to(LATEST)}")
                tip_text = "\n".join(tips) if tips else "- No attachments (SMTP not configured)"

                body = f"""This is a downgraded local-outbox copy because SMTP is not configured.

Case: {cid or "n/a"}
Intent: {intent or "n/a"}

{tip_text}
"""
                mid = a.get("message_id")
                eml = build_minimal_eml(subject=subj if subj.startswith("Re:") else f"Re: {subj}",
                                        body=body,
                                        message_id=mid)
                write_bytes(final_path.as_posix(), eml)
                created += 1

            a["outbox_path_actual"] = str(final_path.relative_to(LATEST))
            a.setdefault("_postprocess", {})["created_eml_if_missing"] = True

        # spam 範例：放一個隔離 placeholder（若沒有）
        if (cid or "").startswith("z_spam"):
            qpath = quar_dir / f"{cid}.eml"
            if not qpath.exists():
                eml = build_minimal_eml(subject=f"[QUARANTINE] {cid}", body="Spam placeholder (no raw eml available).")
                write_bytes(qpath.as_posix(), eml)
                a.setdefault("_postprocess", {})["quarantined_placeholder"] = True

        patched.append(json.dumps(a, ensure_ascii=False))

patched_path = LATEST / "actions.patched.jsonl"
with open(patched_path, "w", encoding="utf-8") as f:
    f.write("\n".join(patched) + "\n")

print(f"[OK] postprocess done on {LATEST}")
print(f"[i] created_outbox_files: {created}")
print(f"[i] actions_patched: {patched_path}")
for p in sorted(outbox_dir.glob("*.eml"))[:50]:
    print(" -", p.relative_to(LATEST))
