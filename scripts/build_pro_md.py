import json, pathlib, glob
root = pathlib.Path("."); pro = root/"reports_auto"/"pro"
def pick_latest():
    p = pro/"latest"/"summary.json"
    if p.exists(): return p
    cands = sorted(glob.glob(str(pro/"pro_*/summary.json")))
    return pathlib.Path(cands[-1]) if cands else None
jpath = pick_latest()
assert jpath is not None, "no pro summary found"
j = json.loads(jpath.read_text("utf-8"))
lines=[]
lines.append("# Pro 評測摘要（" + str(j.get("created_at","")) + "）\n")
def sec_intent(m):
    lines.append("## INTENT\n")
    if m.get("status")!="ok": lines.append("- 狀態：" + str(m.get("status")) + "  \n"); return
    met=m.get("metrics",{})
    lines.append("- n：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n")
    lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
def sec_spam(m):
    lines.append("\n## SPAM\n")
    if m.get("status")!="ok": lines.append("- 狀態：" + str(m.get("status")) + "  \n"); return
    met=m.get("metrics",{})
    lines.append("- n：" + str(m.get("n")) + "  \n- 模型：`" + str(m.get("model_path","")) + "`  \n")
    lines.append("- 準確率：" + "{:.3f}".format(float(met.get("accuracy",0))) + "  \n- Macro-F1：" + "{:.3f}".format(float(met.get("macro_f1",0))) + "\n")
    if "roc_auc" in m: lines.append("- ROC-AUC：" + "{:.3f}".format(float(m.get("roc_auc",0))) + "\n")
    if "pr_auc"  in m: lines.append("- PR-AUC："  + "{:.3f}".format(float(m.get("pr_auc",0)))  + "\n")
    if "ece"     in m: lines.append("- ECE："      + "{:.3f}".format(float(m.get("ece",0)))     + "\n")
    rec=m.get("recommended_threshold")
    if rec: lines.append("- **建議閾值**：" + str(rec.get("threshold")) + "  \n")
def sec_kie(m):
    lines.append("\n## KIE\n")
    lines.append("- 目錄：`" + str(m.get("dir","")) + "`  \n- 狀態：" + str(m.get("status")) + "  \n")
    files=m.get("files",{}); lines.append("- 必要檔：" + json.dumps(files, ensure_ascii=False) + "\n")
    shp=m.get("sample_shapes",{})
    if shp: lines.append("\n- Tensor 樣本形狀：" + json.dumps(shp, ensure_ascii=False) + "\n")
sec_intent(j.get("intent",{})); sec_spam(j.get("spam",{})); sec_kie(j.get("kie",{}))
outdir=jpath.parent
(outdir/"summary.md").write_text("\n".join(lines), "utf-8")
print("[OK] wrote", outdir/"summary.md")
