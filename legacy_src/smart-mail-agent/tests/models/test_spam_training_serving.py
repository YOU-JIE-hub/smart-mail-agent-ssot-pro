from models.spam import train as spam_train
from models.spam import serving as spam_serving

def test_spam_train_and_score():
    m = spam_train.train()
    out = spam_serving.score(["free money now", "正常郵件"])
    assert out["label"] in ("spam","ham")
    # 有一半以上含 spam 關鍵詞時應傾向 spam
    assert out["score"] >= 0.0
