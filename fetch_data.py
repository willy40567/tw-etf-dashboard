"""
fetch_data.py — 從 FinMind 公開 API 抓取台股 ETF 資料，寫入 SQLite

使用方式（在專案目錄下執行）：
    python fetch_data.py                # 抓預設清單（0050, 0056, 00878）
    python fetch_data.py 0050 006208    # 只抓指定代號

FinMind 是免費的台股資料 API（https://finmindtrade.com）。
不註冊也能用，但每小時請求次數較少；
建議免費註冊取得 token，設成環境變數 FINMIND_TOKEN。
"""

import os
import sys
import time

import requests

from database import get_connection

API_URL = "https://api.finmindtrade.com/api/v4/data"
TOKEN = os.environ.get("FINMIND_TOKEN", "")  # 沒有 token 也能跑，只是限流較嚴

DEFAULT_ETFS = ["0050", "0056", "00878"]
START_DATE = "2015-01-01"


def fetch_dataset(dataset: str, stock_id: str, start_date: str) -> list[dict]:
    """呼叫 FinMind API，回傳資料列（list of dict）。"""
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": start_date,
    }
    if TOKEN:
        params["token"] = TOKEN

    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != 200:
        raise RuntimeError(f"API 回傳錯誤：{payload.get('msg')}")
    return payload.get("data", [])


def save_prices(stock_id: str) -> int:
    """抓每日股價，寫入 prices 資料表，回傳筆數。"""
    rows = fetch_dataset("TaiwanStockPrice", stock_id, START_DATE)
    conn = get_connection()
    conn.executemany(
        """
        INSERT OR REPLACE INTO prices
            (stock_id, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["stock_id"], r["date"],
                r["open"], r["max"], r["min"], r["close"],
                r["Trading_Volume"],
            )
            for r in rows
        ],
    )
    conn.commit()
    conn.close()
    return len(rows)


def save_dividends(stock_id: str) -> int:
    """抓除權息結果（現金股利），寫入 dividends 資料表，回傳筆數。"""
    rows = fetch_dataset("TaiwanStockDividendResult", stock_id, START_DATE)
    conn = get_connection()
    conn.executemany(
        """
        INSERT OR REPLACE INTO dividends (stock_id, date, cash_dividend)
        VALUES (?, ?, ?)
        """,
        [
            (r["stock_id"], r["date"], r.get("stock_and_cache_dividend", 0))
            for r in rows
        ],
    )
    conn.commit()
    conn.close()
    return len(rows)


def main() -> None:
    etfs = sys.argv[1:] or DEFAULT_ETFS
    for stock_id in etfs:
        print(f"抓取 {stock_id} ...")
        n_price = save_prices(stock_id)
        time.sleep(1)  # 禮貌性間隔，避免觸發 API 限流
        n_div = save_dividends(stock_id)
        time.sleep(1)
        print(f"  股價 {n_price} 筆、股利 {n_div} 筆 已寫入資料庫")
    print("完成！執行 streamlit run app.py 開啟儀表板。")


if __name__ == "__main__":
    main()
