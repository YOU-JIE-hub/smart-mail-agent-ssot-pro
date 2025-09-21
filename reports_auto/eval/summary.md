# Smart Mail Agent — 煙霧測試摘要（2025-09-21T13:40:04）

## INTENT

- 範例數：6  
- 模型：`/home/youjie/projects/smart-mail-agent-ssot-pro/models/spam/artifacts/model_pipeline.pkl`  
- classes：["其他", "報價", "技術支援", "投訴", "規則詢問", "資料異動"]

- 準確率：0.667  
- Macro-F1：0.583

- **建議閾值**：0.5

## SPAM

- 範例數：2  
- 模型：`/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/spam/artifacts_prod/model_pipeline.pkl`  
- classes：[0, 1]

- 準確率：1.000  
- Macro-F1：1.000

- **建議閾值**：0.15000000000000002

## KIE

- 目錄：`/home/youjie/projects/smart-mail-agent_ssot/artifacts_inbox/kie1/model`  
- 狀態：ok  
- 必要檔：{"config.json": true, "model.safetensors": true, "tokenizer.json": true}

- Tensor 樣本形狀：{"classifier.bias": [9], "classifier.weight": [9, 768], "roberta.embeddings.LayerNorm.bias": [768], "roberta.embeddings.LayerNorm.weight": [768], "roberta.embeddings.position_embeddings.weight": [514, 768], "roberta.embeddings.token_type_embeddings.weight": [1, 768], "roberta.embeddings.word_embeddings.weight": [250002, 768], "roberta.encoder.layer.0.attention.output.LayerNorm.bias": [768]}
