# ARCHITECTURE

資料流：Source → OCR/Scrape → Classify → NLP(LLM 可退化) → Actions(JSON/PDF/Notify/API)

ai_rpa/：CLI ai-rpa（ocr/scraper/nlp/actions）

smart_mail_agent/
- core/：classifier（transformers 懶載）、policy_engine
- routing/：action_handler、run_action_handler
- ingestion/：email_processor、integrations/send_with_attachment
- spam/：spam_filter_orchestrator（canonical）
- utils/：logger/jsonlog/log_writer/pdf_safe/fonts
- observability/sitecustomize：已中性化

Shim 原則：舊路徑只 re-export/別名；新代碼只 import canonical。
