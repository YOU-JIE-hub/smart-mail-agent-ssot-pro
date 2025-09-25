import os, glob
def test_rpa_outputs_exist():
    cands = sorted(glob.glob("reports_auto/e2e_mail/*")+glob.glob("reports_auto/e2e_run/*"), reverse=True)
    assert cands, "no e2e outputs"
    ro = os.path.join(cands[0],"rpa_out")
    assert os.path.isdir(ro), "missing rpa_out/"
    # 子資料夾可依情境為空，但至少其一存在即可
    subdirs = ("tickets","faq_replies","diffs","quotes")
    assert any(os.path.isdir(os.path.join(ro,d)) for d in subdirs), "no rpa subdirs found"
