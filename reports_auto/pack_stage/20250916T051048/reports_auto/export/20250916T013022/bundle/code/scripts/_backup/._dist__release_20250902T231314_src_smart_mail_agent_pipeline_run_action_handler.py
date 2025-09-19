#!/usr/bin/env python3
# 檔案位置
#   src/smart_mail_agent/pipeline/run_action_handler.py
# 模組用途
#   讀取 .eml → Spam/Intent/KIE → 規劃動作 → 產 summary。
from __future__ import annotations

from collections import Counter
from pathlib import Path

from smart_mail_agent.intent.classifier import IntentRouter
from smart_mail_agent.kie.infer import KIE
from smart_mail_agent.spam.ens import SpamEnsemble

from .action_handler import plan_actions


def run_e2e_mail(eml_dir: Path, out_root: Path) -> str:
    """參數: .eml 目錄/out_root；回傳: Markdown 摘要字串。"""
    project_root = Path(__file__).resolve().parents[3]
    cases = []
    for p in sorted(Path(eml_dir).glob("*.eml")):
        t = p.read_text(encoding="utf-8", errors="ignore")
        subj = ""
        body = t
        if "\n\n" in t:
            hdr, body = t.split("\n\n", 1)
            for line in hdr.splitlines():
                if line.lower().startswith("subject:"):
                    subj = line.split(":", 1)[1].strip()
                    break
        cases.append({"id": p.stem, "subject": subj, "body": body})

    clf_spam = SpamEnsemble(project_root)
    clf_intent = IntentRouter(project_root)
    kie = KIE(project_root)
    ens1 = 0
    ens0 = 0
    final = []
    for c in cases:
        text = (c["subject"] or "") + "\n" + (c["body"] or "")
        if clf_spam.predict(text) == 1:
            ens1 += 1
            final.append({"id": c["id"], "intent": "quarantine", "fields": {}})
            continue
        ens0 += 1
        intent = clf_intent.predict(text)
        fields = {"spans": kie.extract(text)}
        final.append({"id": c["id"], "intent": intent, "fields": fields})

    outdir = out_root / "rpa_out"
    plan_actions(final, outdir)
    cnt = Counter([x["intent"] for x in final])
    lines = ["# E2E Summary", f"- total: {len(final)}", f"- spam: {ens1}", f"- clean: {ens0}"]
    for k, v in cnt.items():
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) + "\n"
