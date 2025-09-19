CREATE TABLE IF NOT EXISTS actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, intent TEXT, action TEXT, status TEXT,
  artifact_path TEXT, ext TEXT, message TEXT
);
CREATE VIEW IF NOT EXISTS v_intent_daily AS
SELECT substr(ts,1,8) AS d, intent, count(*) AS n
FROM actions WHERE intent IS NOT NULL GROUP BY d,intent;
CREATE VIEW IF NOT EXISTS v_action_stats AS
SELECT action, count(*) AS n, sum(CASE WHEN status='ok' THEN 1 ELSE 0 END) AS ok_n
FROM actions GROUP BY action;
CREATE VIEW IF NOT EXISTS v_hitl_rate AS
SELECT substr(ts,1,8) AS d, 
       sum(CASE WHEN action='hitl_queue' THEN 1 ELSE 0 END) * 1.0 / count(*) AS hitl_rate
FROM actions GROUP BY d;
CREATE VIEW IF NOT EXISTS v_kie_coverage AS
SELECT substr(ts,1,8) AS d,
       sum(CASE WHEN action IN ('quote_reply','create_ticket') THEN 1 ELSE 0 END) AS acted,
       count(*) AS n
FROM actions GROUP BY d;
