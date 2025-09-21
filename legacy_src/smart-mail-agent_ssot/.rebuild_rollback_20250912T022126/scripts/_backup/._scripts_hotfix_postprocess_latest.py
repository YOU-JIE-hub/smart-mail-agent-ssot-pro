import json, os, sys, pathlib, time
from collections import defaultdict
from hotfix._io_utils import safe_filename, build_minimal_eml, write_bytes, ensure_dir

BASE = pathlib.Path(__file__).resolve().parents[2]
ROOT = BASE / "reports_auto" / "e2e_mail"
LATEST = BASE / "reports_auto" / "e2e_mail" / "LATEST"
if not LATEST.exists():
    # fallback：挑最新一個 timestamp 目錄
    cands = [p for p in ROOT.glob("20*") if p.is_dir()]
    if cands:
        LATEST = sorted(cands)[-1]
    else:
        print("[ERR] no e2e outputs found", file=sys.stderr); sys.exit(2)

cases_path   = LATEST / "cases.jsonl"
actions_path = LATEST / "actions.jsonl"
outbox_dir   = LATEST / "rpa_out" / "email_outbox"
quar_dir     = LATEST / "rpa_out" / "quarantine"

ensure_dir(outbox_dir.as_posix())
ensure_dir(quar_dir.as_posix())

# 載入 cases
cases = {}
if cases_path.exists():
    with open(cases_path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try:
                j = json.loads(line)
                cid = j.get("case_id") or j.get("id") or j.get("case") or j.get("cid")
                if cid:
                    cases[cid] = j
            except Exception:
                pass

# 便利 actions，補 outbox
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
            patched.append(line); 
            continue

        status = a.get("status")
        atype  = a.get("action_type") or a.get("action")
        cid    = a.get("case_id")
        intent = a.get("intent")

        # 只處理 SendEmail 降級（smtp_not_configured）
        if atype == "SendEmail" and (status == "downgraded" or a.get("error")=="smtp_not_configured"):
            # 取得建議檔名
            orig_path = a.get("outbox_path") or a.get("payload_ref") or ""
            base = os.path.basename(orig_path) if orig_path else f"{cid or 'mail'}_{int(time.time())}.eml"
            base = safe_filename(base)
            if not base.lower().endswith(".eml"):
                base += ".eml"
            final_path = outbox_dir / base

            if not final_path.exists():
                subj = None
                # 優先取 cases 的主旨
                c = cases.get(cid or "")
                subj = (c or {}).get("subject") or (c or {}).get("title") or base.replace(".eml","")
                if not subj:
                    subj = base.replace(".eml","")

                # 嘗試找到有關聯的 quote 檔，放進內文提示
                tips = []
                quotes_dir = LATEST / "rpa_out" / "quotes"
                if quotes_dir.exists():
                    for qf in quotes_dir.glob("*.html"):
                        if (cid or "") and (cid in qf.name):
                            tips.append(f"- Quote: {qf.relative_to(LATEST)}")
                if tips:
                    tip_text = "\n".join(tips)
                else:
                    tip_text = "- No attachments (SMTP not configured)"

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

            # 紀錄實際路徑
            a["outbox_path_actual"] = str(final_path.relative_to(LATEST))
            a.setdefault("_postprocess", {})["created_eml_if_missing"] = True

        # （可選）對 spam 進 quarantine 落地 placeholder（不再被 SMTP 影響）
        if (cid or "").startswith("z_spam") and not any((quar_dir / f"{cid}.eml").exists() for _ in [0]):
            qpath = quar_dir / f"{cid}.eml"
            if not qpath.exists():
                eml = build_minimal_eml(subject=f"[QUARANTINE] {cid}", body="Spam placeholder (no raw eml available).")
                write_bytes(qpath.as_posix(), eml)
                a.setdefault("_postprocess", {})["quarantined_placeholder"] = True

        patched.append(json.dumps(a, ensure_ascii=False))

# 輸出 patched 檔，不覆蓋原始
patched_path = LATEST / "actions.patched.jsonl"
with open(patched_path, "w", encoding="utf-8") as f:
    f.write("\n".join(patched) + "\n")

# 稽核輸出
print(f"[OK] postprocess done on {LATEST}")
print(f"[i] created_outbox_files: {created}")
print(f"[i] actions_patched: {patched_path}")
# 列出 outbox 目錄現況
for p in sorted(outbox_dir.glob("*.eml"))[:50]:
    print(" -", p.relative_to(LATEST))
