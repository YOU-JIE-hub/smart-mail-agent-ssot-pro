# Model Card (intent_pro_cal)
- seed: 42
- train: data/intent/i_20250901_merged.jsonl
- model_out: artifacts/intent_pro_cal.pkl
- features: word(1-2) tfidf, char(3-5) tfidf, lexicon & regex flags
- classifier: LinearSVC (balanced) + sigmoid calibration (cv=3)