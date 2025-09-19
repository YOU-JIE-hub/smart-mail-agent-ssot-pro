# -*- coding: utf-8 -*-
import json, os
from pathlib import Path
import joblib
from scipy import sparse

class IntentBundle:
    def __init__(self, root: os.PathLike):
        self.root = Path(root)
        self.manifest = json.loads((self.root/"manifest.json").read_text(encoding="utf-8"))
        self.schema   = json.loads((self.root/"feature_schema.json").read_text(encoding="utf-8"))
        self.bundle   = joblib.load(self.root/"pipeline.joblib")
        self.pipe     = self.bundle["pipeline"]
    def preflight(self):
        sample = "請幫我報價 120000 元，數量 3 台，單號 AB-99127"
        features = self.pipe.named_steps["features"]
        Z = features.transform([sample])
        if not sparse.isspmatrix(Z):
            raise RuntimeError("features.transform did not return sparse matrix")
        got_total = Z.shape[1]; exp = self.manifest["dims"]
        if got_total != exp["total"]:
            raise RuntimeError(f"dim mismatch: total={got_total} expected={exp['total']} "
                               f"(word={exp['word']} char={exp['char']} rules={exp['rules']})")
        return True
    def predict(self, texts):
        return list(self.pipe.predict(texts))
