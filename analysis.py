"""
analysis.py — 分析層：所有 SQL 查詢與指標計算集中在這裡

刻意把分析邏輯用 SQL 寫（而不是全部用 pandas），
原因是：面試時這個檔案就是你展示 SQL 能力的證據——
GROUP BY、JOIN、子查詢都有實際應用場景。
"""

import pandas as pd

from database import get_connection


def load_prices(stock_ids: list[str], start: str, end: str) -> pd.DataFrame:
    """讀取指定 ETF 在日期區間內的收盤價。"""
    placeholders = ",".join("?" * len(stock_ids))
    sql = f"""
        SELECT stock_id, date, close
        FROM prices
        WHERE stock_id IN ({placeholders})
          AND date BETWEEN ? AND ?
        ORDER BY date
    """
    conn = get_connection()
    df = pd.read_sql_query(sql, conn, params=[*stock_ids, start, end])
    conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def annual_returns(stock_ids: list[str], start: str, end: str) -> pd.DataFrame:
    """
    計算各 ETF 的「年度報酬率」（只看價格，不含股利）。

    作法：每年取第一個與最後一個交易日的收盤價，
    用子查詢 + GROUP BY 找出年初／年末價格再相除。
    日期區間與價格圖一致，避免兩張圖看的年份對不上。
    """
    placeholders = ",".join("?" * len(stock_ids))
    sql = f"""
        WITH yearly AS (
            SELECT
                stock_id,
                STRFTIME('%Y', date)            AS year,
                MIN(date)                       AS first_day,
                MAX(date)                       AS last_day
            FROM prices
            WHERE stock_id IN ({placeholders})
              AND date BETWEEN ? AND ?
            GROUP BY stock_id, STRFTIME('%Y', date)
        )
        SELECT
            y.stock_id,
            y.year,
            p1.close AS first_close,
            p2.close AS last_close,
            ROUND((p2.close - p1.close) * 100.0 / p1.close, 2) AS return_pct
        FROM yearly y
        JOIN prices p1 ON p1.stock_id = y.stock_id AND p1.date = y.first_day
        JOIN prices p2 ON p2.stock_id = y.stock_id AND p2.date = y.last_day
        ORDER BY y.year, y.stock_id
    """
    conn = get_connection()
    df = pd.read_sql_query(sql, conn, params=[*stock_ids, start, end])
    conn.close()
    return df


def dividend_history(stock_ids: list[str]) -> pd.DataFrame:
    """各 ETF 的年度配息合計（GROUP BY 年份加總現金股利）。"""
    placeholders = ",".join("?" * len(stock_ids))
    sql = f"""
        SELECT
            stock_id,
            STRFTIME('%Y', date)              AS year,
            ROUND(SUM(cash_dividend), 3)      AS total_dividend,
            COUNT(*)                          AS payout_count
        FROM dividends
        WHERE stock_id IN ({placeholders})
        GROUP BY stock_id, STRFTIME('%Y', date)
        ORDER BY year, stock_id
    """
    conn = get_connection()
    df = pd.read_sql_query(sql, conn, params=stock_ids)
    conn.close()
    return df


def summary_stats(prices: pd.DataFrame) -> pd.DataFrame:
    """
    用 pandas 計算每檔 ETF 的摘要統計：
    累積報酬、年化報酬、年化波動度、最大回撤。
    （這部分用 pandas 比 SQL 自然，展示「工具各有適用場景」的判斷力。）
    """
    results = []
    for stock_id, g in prices.groupby("stock_id"):
        g = g.sort_values("date")
        close = g["close"].reset_index(drop=True)
        daily_ret = close.pct_change().dropna()

        years = (g["date"].iloc[-1] - g["date"].iloc[0]).days / 365.25
        cumulative = close.iloc[-1] / close.iloc[0] - 1
        annualized = (1 + cumulative) ** (1 / years) - 1 if years > 0 else 0
        volatility = daily_ret.std() * (252 ** 0.5)  # 年化波動度

        running_max = close.cummax()
        drawdown = (close - running_max) / running_max
        max_drawdown = drawdown.min()

        results.append({
            "ETF": stock_id,
            "累積報酬率(%)": round(cumulative * 100, 2),
            "年化報酬率(%)": round(annualized * 100, 2),
            "年化波動度(%)": round(volatility * 100, 2),
            "最大回撤(%)": round(max_drawdown * 100, 2),
        })
    return pd.DataFrame(results)


def normalize_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """把各 ETF 價格換算成「期初 = 100」的指數，方便同圖比較。"""
    out = []
    for stock_id, g in prices.groupby("stock_id"):
        g = g.sort_values("date").copy()
        g["index_value"] = g["close"] / g["close"].iloc[0] * 100
        out.append(g)
    return pd.concat(out, ignore_index=True)
