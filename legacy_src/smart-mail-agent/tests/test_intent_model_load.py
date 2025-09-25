import os, json, joblib
def test_intent_model_and_thresholds_loadable():
    assert os.path.exists("artifacts/intent_pro_cal.pkl")
    assert os.path.exists("reports_auto/intent_thresholds.json")
    mdl = joblib.load("artifacts/intent_pro_cal.pkl")
    th = json.load(open("reports_auto/intent_thresholds.json","r",encoding="utf-8"))
    assert isinstance(th, dict) and th
