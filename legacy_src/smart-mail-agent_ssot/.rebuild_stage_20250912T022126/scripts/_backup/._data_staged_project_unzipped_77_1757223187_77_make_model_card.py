#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, re
from pathlib import Path

def parse_eval(p):
    txt = Path(p).read_text(encoding="utf-8")
    m_acc = re.search(r'Accuracy\s*=\s*([\d\.]+)', txt)
    m_mf1 = re.search(r'MacroF1\s*=\s*([\d\.]+)', txt)
    per = {}
    for lab in ["biz_quote","complaint","other","policy_qa","profile_update","tech_support"]:
        m = re.search(rf'^{lab}:\s*P=([\d\.]+)\s*R=([\d\.]+)\s*F1=([\d\.]+).*$', txt, re.M)
        if m: per[lab] = tuple(map(float, m.groups()))
    return (float(m_acc.group(1)) if m_acc else None,
            float(m_mf1.group(1)) if m_mf1 else None,
            per, txt)

def top_confusions(conf_path, k=6):
    rows=[]
    with open(conf_path, "r", encoding="utf-8") as f:
        labs=f.readline().strip().split("\t")[1:]
        mat=[list(map(int, ln.strip().split("\t")[1:])) for ln in f if ln.strip()]
    for i,li in enumerate(labs):
        for j,lj in enumerate(labs):
            if i!=j and mat[i][j]>0:
                rows.append((mat[i][j], f"{li} → {lj}", mat[i][j]))
    rows.sort(reverse=True)
    return [f"{lab} ({cnt})" for _,lab,cnt in rows[:k]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh_eval", required=True)
    ap.add_argument("--tuned_eval", required=True)
    ap.add_argument("--confusion", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    acc0,mf10,per0,_ = parse_eval(args.fresh_eval)
    acc1,mf11,per1,_ = parse_eval(args.tuned_eval)
    thr = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
    conf_top = top_confusions(args.confusion)

    md = []
    md.append("# Intent Classifier (Pro) – Model Card")
    md.append("")
    md.append(f"- Seed: `{args.seed}`")
    md.append(f"- Tuned thresholds: `p1={thr['p1']}`, `margin={thr['margin']}`, `policy_lock={thr['policy_lock']}`")
    md.append(f"- Test set: `{thr.get('tuned_on','(unknown)')}` (n={thr.get('n','?')})")
    md.append("")
    md.append("## Metrics")
    md.append(f"- Before thresholds: **Accuracy {acc0:.4f} / MacroF1 {mf10:.4f}**")
    md.append(f"- After thresholds:  **Accuracy {acc1:.4f} / MacroF1 {mf11:.4f}**  _(ΔAcc {acc1-acc0:+.4f}, ΔMacroF1 {mf11-mf10:+.4f})_")
    md.append("")
    md.append("### Per-class (after thresholds)")
    for lab in ["biz_quote","complaint","other","policy_qa","profile_update","tech_support"]:
        if lab in per1:
            P,R,F = per1[lab]
            md.append(f"- **{lab}**: P={P:.3f} / R={R:.3f} / F1={F:.3f}")
    md.append("")
    md.append("### Top confusions")
    if conf_top:
        for s in conf_top: md.append(f"- {s}")
    else:
        md.append("- (no off-diagonal errors)")
    md.append("")
    md.append("## Environment")
    env = Path("reports_auto/env_versions.json")
    if env.exists():
        md.append("```json")
        md.append(env.read_text(encoding="utf-8").strip())
        md.append("```")
    Path("model_card_pro.md").write_text("\n".join(md), encoding="utf-8")
    print("[CARD] model_card_pro.md")
if __name__ == "__main__":
    main()
