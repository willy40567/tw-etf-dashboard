# 台股 ETF 比較儀表板

用 Python + SQLite + Streamlit 打造的台股 ETF 分析儀表板。
從 FinMind 公開 API 抓取股價與配息資料，寫入 SQLite，
以 SQL 進行年度報酬與配息彙總分析，最後用 Streamlit 視覺化呈現。

> 線上 Demo：（部署到 Streamlit Cloud 後把連結貼在這裡）

## 功能

- 多檔 ETF 同圖比較（價格標準化為期初 = 100）
- 年度報酬率長條圖（SQL 子查詢 + GROUP BY 計算）
- 年度配息合計與配息次數
- 摘要統計：累積報酬、年化報酬、年化波動度、最大回撤

## 系統架構

```
FinMind API ──> fetch_data.py ──> SQLite (etf.db)
                                      │
                                 analysis.py（SQL + pandas）
                                      │
                                  app.py（Streamlit 儀表板）
```

| 檔案 | 職責 |
|---|---|
| `database.py` | 資料庫連線與資料表結構（prices、dividends） |
| `fetch_data.py` | ETL：呼叫 API → 清洗欄位 → 寫入 SQLite |
| `analysis.py` | 分析層：SQL 查詢與指標計算 |
| `app.py` | 展示層：Streamlit 互動式儀表板 |

## 快速開始

```bash
# 1. 安裝套件
pip install -r requirements.txt

# 2. 抓取資料（預設 0050 / 0056 / 00878，可自行指定代號）
python fetch_data.py
python fetch_data.py 0050 006208 00713   # 範例：自訂清單

# 3. 啟動儀表板
streamlit run app.py
```

（選用）FinMind 免費註冊後可取得 token 放寬 API 限流：

```bash
export FINMIND_TOKEN=你的token        # Windows 用 set
```

## 部署到 Streamlit Community Cloud

1. 把這個專案推上 GitHub（`etf.db` 已被 `.gitignore` 排除，不進版控）
2. 到 https://share.streamlit.io 用 GitHub 帳號登入
3. New app → 選這個 repo → Main file 填 `app.py` → Deploy
4. 雲端環境第一次沒有 `etf.db`，有兩種作法：
   - 快速展示：本機跑完 `python fetch_data.py` 後，用 `git add -f etf.db`
     強制提交一份資料快照
   - 較乾淨：另接排程或在啟動時呼叫 `fetch_data.py` 重新抓取

## 免責聲明

本專案僅供學習與作品集展示，不構成任何投資建議。
