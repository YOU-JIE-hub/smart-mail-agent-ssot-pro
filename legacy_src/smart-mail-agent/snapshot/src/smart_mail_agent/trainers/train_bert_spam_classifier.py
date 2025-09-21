from __future__ import annotations

"""
Import-safe BERT spam trainer.
- No file I/O or heavy work at import time.
- Optional deps (transformers / datasets / sklearn) are guarded.
- Call `train_bert_spam_classifier(...)` to actually train.
"""

# ----- Optional dependencies (clean guards) -----
_TRANSFORMERS_AVAILABLE = False
try:
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    _TRANSFORMERS_AVAILABLE = True
except Exception:  # pragma: no cover
    AutoTokenizer = AutoModelForSequenceClassification = Trainer = TrainingArguments = None  # type: ignore

_DATASETS_AVAILABLE = False
try:
    from datasets import load_dataset  # type: ignore

    _DATASETS_AVAILABLE = True
except Exception:  # pragma: no cover

    def load_dataset(*_a, **_k):
        raise RuntimeError("`datasets` not installed. Install with: pip install datasets")


_SKLEARN_AVAILABLE = False
try:
    from sklearn.utils import shuffle  # noqa: F401

    _SKLEARN_AVAILABLE = True
except Exception:  # pragma: no cover

    def shuffle(*_a, **_k):
        raise RuntimeError("`scikit-learn` not installed. Install with: pip install scikit-learn")


# ----- Public API -----
def train_bert_spam_classifier(
    dataset_name_or_path: str,
    *,
    model_name: str = "bert-base-uncased",
    text_field: str = "text",
    label_field: str = "label",
    output_dir: str = "out/bert_spam",
    epochs: int = 1,
    batch_size: int = 8,
) -> None:
    """
    Simple BERT fine-tune example.
    `dataset_name_or_path` can be a HF dataset name OR a JSON/JSONL file path
    with fields `text` and `label`.
    """
    if not _TRANSFORMERS_AVAILABLE:
        raise RuntimeError("`transformers` not installed. Install with: pip install transformers")
    if not _DATASETS_AVAILABLE:
        raise RuntimeError("`datasets` not installed. Install with: pip install datasets")

    # Load dataset (lazy & explicit; no import-time I/O)
    if dataset_name_or_path.endswith(".json") or dataset_name_or_path.endswith(".jsonl"):
        ds = load_dataset("json", data_files=dataset_name_or_path)
    else:
        ds = load_dataset(dataset_name_or_path)

    tok = AutoTokenizer.from_pretrained(model_name)

    def tokenize(batch):
        return tok(batch[text_field], truncation=True, padding="max_length")

    ds = ds.map(tokenize)

    model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)

    args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=batch_size,
        num_train_epochs=epochs,
        evaluation_strategy="no",
        save_strategy="no",
        logging_strategy="no",
        report_to="none",
    )
    trainer = Trainer(model=model, args=args, train_dataset=ds["train"])
    trainer.train()


__all__ = ["train_bert_spam_classifier"]
