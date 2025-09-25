import json

from datasets import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

# 類別對應（順序需與原標籤一致）
LABELS = ["請求技術支援", "申請修改資訊", "詢問流程或規則", "投訴與抱怨", "業務接洽或報價", "其他"]
label2id = {label: i for i, label in enumerate(LABELS)}
id2label = {i: label for i, label in enumerate(LABELS)}

# 路徑設定
DATA_PATH = "data/train/emails_train.json"
MODEL_OUT = "model/roberta-zh-checkpoint"
PRETRAINED_MODEL = "bert-base-chinese"

# 載入資料
with open(DATA_PATH, encoding="utf-8") as f:
    raw_data = json.load(f)
for row in raw_data:
    row["label"] = label2id[row["label"]]

# 建立 Dataset
dataset = Dataset.from_list(raw_data)

# 分詞器
tokenizer = AutoTokenizer.from_pretrained(PRETRAINED_MODEL)


def tokenize(batch):
    return tokenizer(
        batch["subject"] + "\n" + batch["content"],
        truncation=True,
        padding="max_length",
        max_length=256,
    )


encoded_dataset = dataset.map(tokenize)

# 模型初始化
model = AutoModelForSequenceClassification.from_pretrained(
    PRETRAINED_MODEL, num_labels=len(LABELS), label2id=label2id, id2label=id2label
)

# 訓練參數
args = TrainingArguments(
    output_dir=MODEL_OUT,
    per_device_train_batch_size=8,
    learning_rate=2e-5,
    num_train_epochs=5,
    logging_dir="./logs",
    logging_steps=10,
    save_strategy="epoch",
    report_to="none",
)

# Trainer
trainer = Trainer(model=model, args=args, train_dataset=encoded_dataset, tokenizer=tokenizer)

# 開始訓練
trainer.train()  # type: ignore[attr-defined]

# 儲存模型與 tokenizer
model.save_pretrained(MODEL_OUT)
tokenizer.save_pretrained(MODEL_OUT)

print(f"模型已儲存至：{MODEL_OUT}")
