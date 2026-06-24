"""
database.py — SQLite 資料庫初始化與連線管理

整個專案使用單一檔案的 SQLite（etf.db），
本地開發零設定，部署到 Streamlit Cloud 時也能直接使用。
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "etf.db"

# 資料表結構：
# prices    — 每日收盤價（一檔 ETF 一天一筆）
# dividends — 除息紀錄（現金股利）
SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    stock_id TEXT NOT NULL,          -- ETF 代號，例如 0050
    date     TEXT NOT NULL,          -- 交易日 YYYY-MM-DD
    open     REAL,
    high     REAL,
    low      REAL,
    close    REAL,
    volume   INTEGER,
    PRIMARY KEY (stock_id, date)
);

CREATE TABLE IF NOT EXISTS dividends (
    stock_id      TEXT NOT NULL,
    date          TEXT NOT NULL,     -- 除息日
    cash_dividend REAL,              -- 每單位現金股利
    PRIMARY KEY (stock_id, date)
);

CREATE INDEX IF NOT EXISTS idx_prices_stock_date ON prices (stock_id, date);
"""


def get_connection() -> sqlite3.Connection:
    """取得資料庫連線，並確保資料表存在。"""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


if __name__ == "__main__":
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    print("資料庫初始化完成，現有資料表：", [t[0] for t in tables])
    conn.close()
