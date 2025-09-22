from pathlib import Path
from models.intent import train as intent_train
from models.intent import serving as intent_serving

def test_intent_train_and_predict(tmp_path, monkeypatch):
    # 使用內建小數據直接訓練
    m = intent_train.train()
    assert "labels" in m and "keywords" in m
    out = intent_serving.predict("想洽談合作並詢問報價")
    labs = out["labels"]
    assert any(x in labs for x in ("sales","quote"))
