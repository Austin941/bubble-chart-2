# 泡泡圖 2.0 (Bubble Chart 2.0) - API 串接說明書 (API Documentation)

本專案的所有籌碼與交易資料皆採用 **全靜態化 (100% Static / Serverless)** 的方式，透過 GitHub Pages 與 `raw.githubusercontent.com` 進行託管。這意味著：

1. **無跨域限制 (No CORS Issue)**：任何前端網站、APP 或後端伺服器皆可直接發出 HTTP GET 請求取得資料。
2. **極高可用性**：資料由 GitHub 全球 CDN 支援，無須擔心 API Server 崩潰。
3. **每日自動更新**：資料會由 GitHub Actions 於每個交易日盤後自動抓取並推播更新。

如果您是其他網站或應用程式的開發者，想要無縫串接並正確應用這些開源資料，請參考以下 API 端點與存取邏輯：

---

## 🔗 基本存取路徑 (Base URL)

所有的 API 端點皆為靜態檔案，根目錄為：
`https://raw.githubusercontent.com/Austin941/bubble-chart-2/master/`

---

## 📈 1. 歷史大戶與散戶持股比例 (Holders History)

本端點提供每檔股票歷史至今的「大戶 (Whale) 與散戶 (Retail) 持股比例」。

- **Method**: `GET`
- **Path**: `data/holders/history/{stock_id}.json` (例如: `2330.json`)
- **Format**: `JSON Array`

### 資料範例：
```json
[
  {
    "date": "20260807",      // 交易日期 (YYYYMMDD)
    "whale": 69.14,          // 大戶持股百分比 (%)
    "retail": 30.86,         // 散戶持股百分比 (%)
    "big_vs_retail": 38.28   // 大戶與散戶的比例差 (whale - retail)
  }
]
```

### 💡 開發者注意事項：
- **歷史相容性**：因資料源 (Yahoo Finance) 曾有改版，若您在存取較早期的歷史資料時遇到 `retail` 或 `retail_pct` 為 `0.0`，請在您的程式碼端自動使用 `100.0 - whale` 來推算正確的散戶比例。雖然我們已在資料庫端修復過一次，但建議您保留此防呆邏輯。

---

## 📊 2. 券商、法人、資券與當沖歷史明細 (Brokers History)

本端點提供所有股票歷史的「各分點券商買賣超」、「三大法人買賣超」、「融資融券」與「當沖」明細。為支援大數據與前端高效能分析，此檔案採用 Apache Parquet 格式壓縮。

- **Method**: `GET`
- **Path**: `data/brokers_history.parquet`
- **Format**: `Apache Parquet`

### 資料欄位 Schema：
| 欄位名稱 (Column) | 型態 (Type) | 說明 (Description) |
| :--- | :--- | :--- |
| `date` | `string` | 交易日期 (格式: YYYYMMDD) |
| `stock_id` | `string` | 股票代號 (例如: "2330") |
| `broker_name` | `string` | 券商分點名稱，或虛擬券商標籤 (見下方說明) |
| `buy` | `int64` | 買進張數/股數 (視爬蟲單位而定，目前皆為股數) |
| `sell` | `int64` | 賣出張數/股數 (視爬蟲單位而定，目前皆為股數) |
| `net` | `int64` | 淨買賣超 ( buy - sell ) |

### 💡 開發者注意事項 (虛擬券商標籤)：
為了統一 Schema 結構，我們將「三大法人」、「資券」與「當沖」轉化為帶有前綴的虛擬券商 (Pseudo-Broker)，存放在 `broker_name` 欄位中。您在查詢時必須使用精準的字串比對：

1. **三大法人 (Institutional)**：
   - 外資：`法人-外資`
   - 投信：`法人-投信`
   - 自營商：`法人-自營商`
2. **信用資券 (Margin & Short)**：
   - 融資：`信用-融資`
   - 融券：`信用-融券`
3. **當沖 (Daytrade)**：
   - 當沖：`信用-當沖`
   - **⚠️ 極度重要 (CRITICAL) ⚠️**：當沖資料代表當日的「當沖總量」，因此 `buy` 欄位會記錄當沖總股數，而 **`net` 欄位永遠為 0**。若您的網站或圖表要渲染當沖歷史，請務必 **`SELECT buy FROM ... WHERE broker_name = '信用-當沖'`**，絕對不要去讀取 `net`，否則當沖數據將全部顯示為 0。

---

## 🛠️ 最佳串接實踐 (Best Practices)

### 前端直接讀取 (Web Frontend)
如果您是開發純前端 (React, Vue, Vanilla JS) 網站，建議使用 **DuckDB-WASM** 搭配 HTTP Range Requests 存取 `.parquet`。這樣前端不需下載整包數百 MB 的 Parquet，只需下載需要的 Bytes 即可秒速渲染圖表。

### 後端或資料分析 (Python / Data Science)
若您使用 Python 進行量化分析或機器學習模型訓練，可以利用 `pandas` 原生支援 HTTP 讀取的特性：
```python
import pandas as pd
import requests

# 1. 讀取大戶散戶 JSON
url_holders = "https://raw.githubusercontent.com/Austin941/bubble-chart-2/master/data/holders/history/2330.json"
df_holders = pd.DataFrame(requests.get(url_holders).json())

# 2. 讀取籌碼歷史 Parquet
url_brokers = "https://raw.githubusercontent.com/Austin941/bubble-chart-2/master/data/brokers_history.parquet"
df_brokers = pd.read_parquet(url_brokers)

# 篩選 2330 的當沖歷史
df_2330_daytrade = df_brokers[(df_brokers['stock_id'] == '2330') & (df_brokers['broker_name'] == '信用-當沖')]
# 記得當沖要讀取 buy 欄位！
print(df_2330_daytrade[['date', 'buy']])
```
