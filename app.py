"""
app.py — 台股 ETF 比較儀表板（Streamlit）

執行方式：
    1. python fetch_data.py        # 第一次先抓資料
    2. streamlit run app.py        # 開啟儀表板
"""

import datetime as dt

import pandas as pd
import streamlit as st

from analysis import (
    annual_returns,
    dividend_history,
    load_prices,
    normalize_prices,
    summary_stats,
)
from database import get_connection
from fetch_data import DEFAULT_ETFS, save_dividends, save_prices

st.set_page_config(page_title="台股 ETF 比較儀表板", page_icon="📈", layout="wide")


# ---------- 資料準備 ----------

@st.cache_data(ttl=3600)
def available_etfs() -> list[str]:
    """從資料庫列出已抓取的 ETF 代號。"""
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT stock_id FROM prices ORDER BY stock_id").fetchall()
    conn.close()
    return [r[0] for r in rows]


etf_list = available_etfs()

if not etf_list:
    st.warning("資料庫是空的（雲端環境第一次啟動時很正常）。")
    st.caption("可以直接在這裡抓預設清單，或在終端機執行 `python fetch_data.py`。")
    if st.button(f"抓取預設 ETF（{'、'.join(DEFAULT_ETFS)}）", type="primary"):
        progress = st.empty()
        for stock_id in DEFAULT_ETFS:
            progress.write(f"抓取 {stock_id} …")
            save_prices(stock_id)
            save_dividends(stock_id)
        progress.write("完成！")
        available_etfs.clear()  # 清掉 cache，讓下面重新讀到資料
        st.rerun()
    st.stop()


# ---------- 側邊欄：使用者選項 ----------

with st.sidebar:
    st.header("查詢條件")
    selected = st.multiselect("選擇 ETF（可多選比較）", etf_list, default=etf_list[:2])
    start_date = st.date_input("起始日期", dt.date(2018, 1, 1))
    end_date = st.date_input("結束日期", dt.date.today())
    st.caption("資料來源：FinMind 公開 API（每日收盤）")

if not selected:
    st.info("請至少選擇一檔 ETF。")
    st.stop()


# ---------- 主畫面 ----------

st.title("台股 ETF 比較儀表板")
st.caption("價格走勢、年度報酬與配息紀錄，一頁看完。價格報酬未含股利再投入。")

prices = load_prices(selected, str(start_date), str(end_date))

if prices.empty:
    st.warning("這個日期區間查不到資料，請調整起訖日期。")
    st.stop()

# 1. 摘要統計卡片
st.subheader("摘要統計")
stats = summary_stats(prices)
cols = st.columns(len(stats))
for col, (_, row) in zip(cols, stats.iterrows()):
    with col:
        st.metric(
            label=f"{row['ETF']} 年化報酬率",
            value=f"{row['年化報酬率(%)']} %",
            delta=f"最大回撤 {row['最大回撤(%)']} %",
            delta_color="off",
        )
st.dataframe(stats, hide_index=True, use_container_width=True)

# 2. 價格走勢（期初 = 100 標準化，方便不同價位的 ETF 同圖比較）
st.subheader("價格走勢（期初 = 100）")
norm = normalize_prices(prices)
chart_df = norm.pivot(index="date", columns="stock_id", values="index_value")
st.line_chart(chart_df)

# 3. 年度報酬率
st.subheader("年度報酬率（%）")
yearly = annual_returns(selected, str(start_date), str(end_date))
yearly_pivot = yearly.pivot(index="year", columns="stock_id", values="return_pct")
st.bar_chart(yearly_pivot)
with st.expander("查看年度報酬明細"):
    st.dataframe(yearly, hide_index=True, use_container_width=True)

# 4. 配息紀錄
st.subheader("年度配息合計（元 / 單位）")
divs = dividend_history(selected)
if divs.empty:
    st.info("選取的 ETF 沒有配息資料。")
else:
    div_pivot = divs.pivot(index="year", columns="stock_id", values="total_dividend")
    st.bar_chart(div_pivot)
    with st.expander("查看配息明細"):
        st.dataframe(divs, hide_index=True, use_container_width=True)

st.divider()
st.caption("本儀表板僅供學習與作品集展示，不構成任何投資建議。")
