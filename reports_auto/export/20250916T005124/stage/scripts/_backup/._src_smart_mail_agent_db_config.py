import os


def get_db_url():
    # 優先環境變數，其次 .env，最後 sqlite
    url = os.getenv("SMA_DB_URL")
    if not url:
        url = "sqlite:///reports_auto/sma.sqlite3"
    # SQLite 目錄保險
    if url.startswith("sqlite:///"):
        os.makedirs("reports_auto", exist_ok=True)
    return url
