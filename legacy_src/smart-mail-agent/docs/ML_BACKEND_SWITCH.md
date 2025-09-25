# 切換到 ML 後端（不破壞既有測試）
```bash
pip install -U scikit-learn joblib
make train-ml-all

# 推論切到 ML（未設定就仍走規則）
export SMA_INTENT_BACKEND=ml
export SMA_SPAM_BACKEND=ml
