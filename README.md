# Bubble Chart 2.0 (泡泡圖 2.0) - Developer & AI Instruction Manual

> **[AI 系統指令 / System Prompt for AI Agents]**
> 若您是未來接手此專案的 AI 開發助理，請務必先詳細閱讀本章節。
> 本專案的核心精神是 **「100% 靜態化、Serverless、極致效能」**。
> 
> **核心架構限制與開發鐵律 (Architecture Constraints & Rules)：**
> 1. **禁止使用任何動態後端**：沒有 Node.js API，沒有 Python API，沒有傳統資料庫 (MySQL/Postgres/Firebase)。所有的資料抓取與處理，**僅限於** GitHub Actions 每天定時執行的 Python 爬蟲腳本 (`scripts/*.py`)。
> 2. **前端資料讀取**：前端 (`simple_history.html`) 完全透過 HTTP Range Requests 讀取靜態檔案（特別是 `.parquet` 與 `.json`）。
> 3. **SQL 查詢處理**：所有的資料過濾、彙整 (GroupBy)、跨日統計，都是由前端的 **DuckDB-WASM** 負責。前端直接以 SQL 語法向 `.parquet` 檔案發出查詢，達到極速響應。
> 4. **虛擬分點 (Pseudo-Brokers)**：請記住，我們的 `history.parquet` 不只存一般券商分點，我們將「三大法人」與「信用資券」都寫入為虛擬的 Broker 名稱：
>    - `法人-外資`, `法人-投信`, `法人-自營商`, `外資自營商`
>    - `信用-融資`, `信用-融券`, `信用-當沖` (當沖的 net 值為 0)
> 5. **絕對禁止假資料 (Strict Anti-Mock Rule)**：若缺少某欄位或歷史資料，必須去寫/改 Python 爬蟲腳本，從源頭產出靜態檔案。絕對禁止在前端介面寫死假數據來填補版面。

---

## 📖 給第三方開發者的 API 串接說明書
如果您是想要串接本資料庫的外部開發者，請務必閱讀 👉 **[API 串接說明書 (API Documentation)](./API_DOCUMENTATION.md)**，內含 API 端點、CORS 說明、Python / JS 讀取範例，以及極為重要的「虛擬券商標籤」與「當沖讀取」規則防呆指南！

---

## 📂 專案目錄結構 (Directory Structure)

```text
📁 bubble-chart-2/
├── 📄 simple_history.html       # 核心前端介面 (UI, Chart.js, DuckDB-WASM 邏輯)
├── 📁 data/                     # 全靜態資料庫 (GitHub Pages 託管)
│   ├── 📄 brokers_history.parquet # 歷史買賣超、法人、資券的核心時間序列資料庫 (DuckDB 查詢目標)
│   ├── 📄 capital_events.json     # 個股除權息與還原係數表
│   ├── 📄 index.json              # 台股總清單快取
│   └── 📁 holders/                # 大戶與散戶持股比例 (JSON)
│       ├── 📄 latest_holders.json # 最新一週大戶籌碼快照
│       └── 📁 history/            # 每檔股票的歷史大戶持股時間序列 (例如: 2330.json)
├── 📁 scripts/                  # 後端資料抓取腳本 (由 GitHub Actions 執行)
│   ├── 📄 fetch_yahoo_brokers.py  # 每日抓取 Yahoo 盤後籌碼/法人/資券/當沖 (核心爬蟲)
│   ├── 📄 backfill_yahoo_history.py # 一次性補齊過去一年歷史資料的腳本
│   └── 📄 fetch_holders.py        # 集保中心大戶籌碼爬蟲
└── 📁 .github/workflows/        # 自動化排程設定 (CI/CD)
    ├── 📄 fetch_yahoo.yml         # 每日台灣時間 20:00 執行抓取與 Git Commit
    └── 📄 backfill_yahoo.yml      # 手動觸發的回補腳本
```

## 🛠️ 本地開發與測試 (Local Development)

由於前端使用 DuckDB-WASM，會受到瀏覽器跨域 (CORS) 與本地檔案協定的安全限制（不能直接點擊兩下開啟 `.html` 檔案），開發時**必須**啟動本地伺服器。

1. **啟動測試伺服器**：
   在專案根目錄開啟終端機，執行：
   ```bash
   python -m http.server 8999
   ```
2. **開啟網頁**：
   在瀏覽器中前往 `http://localhost:8999/simple_history.html` 即可開始測試。

## 📊 前端圖表與渲染邏輯 (Frontend Rendering Logic)

目前的介面使用 `Chart.js` 進行動態繪圖。如果在未來的開發中需要新增圖表：
1. **獲取資料**：
   - 針對 `.parquet` 檔案：撰寫 SQL 透過 `conn.query(query)` 抓取。
   - 針對 `.json` 檔案：使用一般的 `fetch()` 抓取。
2. **圖表生命週期管理**：
   在前端宣告了 `chartInstances` 物件來追蹤 `Chart` 實例。在使用者重新搜尋股票時，**必須先呼叫 `.destroy()`** 銷毀舊圖表，再重新繪製，以防止記憶體洩漏與畫面重疊。

## 🤖 爬蟲開發指南 (Scraping Guidelines)

- **防封鎖機制**：所有對外請求 (尤其是 Yahoo, TWSE 等) **必須**包含 `headers={'User-Agent': ...}`，並在迴圈中加入 `time.sleep(random.uniform(1.5, 3.0))` 隨機延遲。
- **寫入 Parquet**：所有對 `brokers_history.parquet` 的操作，必須先以 `pandas` 讀出舊檔案，與新抓取的 DataFrame 進行 `pd.concat` 並 `drop_duplicates`，最後再利用 `pyarrow.parquet` 寫回，以確保資料不遺失且不重複。

---

*這是一份會與專案共同成長的活文件，開發者與 AI 助理應在每次架構有重大變更時，同步更新本說明書。*
