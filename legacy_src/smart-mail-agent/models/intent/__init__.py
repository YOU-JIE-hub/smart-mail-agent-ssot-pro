# 讓 `from models.intent import train as intent_train` 取得的是子模組
from . import train as train
from .train import load, predict  # 函式另外提供
__all__ = ["train","load","predict"]
