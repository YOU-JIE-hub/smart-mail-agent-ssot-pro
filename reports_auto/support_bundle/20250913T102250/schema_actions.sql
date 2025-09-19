CREATE TABLE actions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT, mail_id TEXT, intent TEXT, action TEXT,
      hash TEXT UNIQUE, status TEXT, artifact_path TEXT, external_ref TEXT, error TEXT, latency_ms REAL
    , ext TEXT, message TEXT);
