PRAGMA journal_mode=WAL;

-- 可選：郵件基本資訊（便於關聯）
CREATE TABLE IF NOT EXISTS mails(
  mail_id TEXT PRIMARY KEY,
  subject TEXT,
  sender TEXT,
  received_at TEXT
);

-- 動作審計（RPA 行為落點）
CREATE TABLE IF NOT EXISTS actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mail_id TEXT,
  action TEXT,
  params_json TEXT,
  status TEXT,
  retries INTEGER DEFAULT 0,
  started_at TEXT,
  finished_at TEXT,
  UNIQUE(mail_id, action)
);

-- LLM 呼叫審計（你要求的 llm_calls）
CREATE TABLE IF NOT EXISTS llm_calls(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mail_id TEXT,
  stage TEXT,            -- classify / extract / plan / act / tri-eval...
  model TEXT,            -- gpt-4o-mini / rules / sklearn-xxx 等
  input_tokens INTEGER,
  output_tokens INTEGER,
  total_tokens INTEGER,
  latency_ms INTEGER,
  cost_usd REAL,
  request_id TEXT,
  created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_actions_mail ON actions(mail_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_mail ON llm_calls(mail_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_stage ON llm_calls(stage);
