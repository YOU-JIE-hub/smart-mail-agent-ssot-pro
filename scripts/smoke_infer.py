import os, joblib, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
p_int = ROOT/"models/intent/artifacts/model_pipeline.pkl"
p_spm = ROOT/"models/spam/artifacts/model_pipeline.pkl"
m_int = joblib.load(p_int)
m_spm = joblib.load(p_spm)
print("intent:", m_int.predict(["請問你們的客服電話？"])[0])
print("spam  :", m_spm.predict(["FREE $$$ click here!!!"])[0])
open(ROOT/"reports_auto/SMOKE_OK","w").write("ok")
