import json
def test_ens_thresholds_ok():
    d = json.load(open("artifacts_prod/ens_thresholds.json","r",encoding="utf-8"))
    assert isinstance(d, dict) and d, "empty ens thresholds"
    for k,v in d.items():
        assert isinstance(v,(int,float)) and 0.0 <= float(v) <= 1.0
