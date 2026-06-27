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


def _adj_factor(date: str, events: list[tuple[str, float]]) -> float:
    """後復權因子：把除權息／分割「除權日之後」的所有比例累乘起來。

    每個事件提供一個比例 = 除權後參考價 / 除權前價（通常略小於 1，
    分割則明顯小於 1，例如 1 拆 4 約 0.25）。某一天的還原因子等於
    所有「除權日晚於這一天」的事件比例乘積，因此最近一筆價格因子為 1
    （不動），越往回被縮放得越多，序列就不會在分割／除息當天斷崖。
    """
    factor = 1.0
    for ex_date, ratio in events:
        if ex_date > date:
            factor *= ratio
    return factor


def ingest(stock_id: str) -> tuple[int, int]:
    """抓單一 ETF 的股價、配息、分割，算好還原價後一次寫入。

    回傳 (股價筆數, 配息筆數)。除權息與分割都提供 before/after 參考價，
    用 after/before 當調整比例，統一處理現金股利、配股與分割。
    """
    prices = fetch_dataset("TaiwanStockPrice", stock_id, START_DATE)
    time.sleep(0.5)  # 禮貌性間隔，避免觸發 API 限流
    dividends = fetch_dataset("TaiwanStockDividendResult", stock_id, START_DATE)
    time.sleep(0.5)
    splits = fetch_dataset("TaiwanStockSplitPrice", stock_id, START_DATE)

    events = [
        (r["date"], r["after_price"] / r["before_price"])
        for r in (*dividends, *splits)
        if r.get("before_price") and r.get("after_price")
    ]

    conn = get_connection()
    conn.executemany(
        """
        INSERT OR REPLACE INTO prices
            (stock_id, date, open, high, low, close, adj_close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                r["stock_id"], r["date"],
                r["open"], r["max"], r["min"], r["close"],
                round(r["close"] * _adj_factor(r["date"], events), 4),
                r["Trading_Volume"],
            )
            for r in prices
        ],
    )
    conn.executemany(
        """
        INSERT OR REPLACE INTO dividends (stock_id, date, cash_dividend)
        VALUES (?, ?, ?)
        """,
        [
            (r["stock_id"], r["date"], r.get("stock_and_cache_dividend", 0))
            for r in dividends
        ],
    )
    conn.commit()
    conn.close()
    return len(prices), len(dividends)


def main() -> None:
    etfs = sys.argv[1:] or DEFAULT_ETFS
    for stock_id in etfs:
        print(f"抓取 {stock_id} ...")
        n_price, n_div = ingest(stock_id)
        print(f"  股價 {n_price} 筆、股利 {n_div} 筆 已寫入資料庫（含還原價）")
        time.sleep(1)
    print("完成！執行 streamlit run app.py 開啟儀表板。")


if __name__ == "__main__":
    main()
