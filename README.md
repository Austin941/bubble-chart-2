# 泡泡圖 2.0 (Bubble Chart 2.0)

這是一個基於全端 Serverless 架構、純靜態且極度高效的台股「大戶籌碼與券商分點」視覺化追蹤平台。
拋棄了傳統的資料庫伺服器，我們採用 **DuckDB-WASM** 搭配 **Parquet** 以及原生 **JSON** 靜態檔案，實現了極速的千檔股票即時歷史查詢。

## ✨ 核心特色與架構

1. **零後端伺服器 (Serverless & Static)**
   - 前端採用純 HTML/JS 搭配 **DuckDB-WASM**，直接在瀏覽器記憶體中高效分析百萬筆券商交易歷史 (`brokers_history.parquet`)。
   - 大戶籌碼與個股基本資料採用靜態 JSON 快取 (`latest_holders.json`, `index.json`)，速度極快且沒有 API 費用。

2. **「虛擬分點」架構 (Pseudo-Brokers)**
   除了全台灣上千家真實的券商分點外，系統更獨創將「全市場籌碼」打包成以下虛擬分點，無縫整合進歷史圖表中：
   - `法人-外資` / `法人-投信` / `法人-自營商`
   - `信用-融資` / `信用-融券`

3. **雙軌歷史回補與自動化更新**
   - **日常更新** (`fetch_yahoo.yml`)：全自動透過 GitHub Actions 每天下午與每週五抓取 TWSE/TPEx 官方 API 與 TDCC 集保中心資料，不依賴任何付費第三方 (如 FinMind)。
   - **歷史回補** (`backfill_yahoo.yml`)：支援透過雲端手動觸發回補 Yahoo Finance 的長天期籌碼與資券歷史，自動繞過封鎖並寫入資料庫。

## 🚀 快速開始

### 1. 本機啟動開發伺服器
由於牽涉到 WASM 載入與跨域 (CORS) 限制，請勿直接雙擊開啟 HTML。請使用 Python 啟動本機伺服器：
```bash
# 開啟終端機並切換到專案資料夾
python -m http.server 8999

# 接著在瀏覽器打開：
http://localhost:8999/simple_history.html
```

### 2. 爬蟲腳本手動測試
所有爬蟲腳本皆放置於 `scripts/` 目錄，支援單獨執行：
```bash
pip install -r scripts/requirements.txt

# 1. 抓取集保大戶籌碼 (TDCC)
python scripts/fetch_holders.py

# 2. 抓取全市場券商分點、三大法人、信用資券 (Yahoo/TWSE/TPEx)
python scripts/fetch_yahoo_brokers.py

# 3. 更新股票代碼與股本資訊
python scripts/fetch_capital_events.py
```

## 📂 檔案與資料庫結構

```text
├── simple_history.html        # 主力前端介面 (Apple-style UI & DuckDB)
├── data/
│   ├── brokers_history.parquet # 核心資料庫 (儲存所有券商、法人、資券的歷史買賣)
│   ├── index.json              # 股票代碼清單快取
│   ├── capital_events.json     # 個股名稱與股本資訊
│   └── holders/
│       ├── latest_holders.json # 最新一週大戶與散戶持股比例 (即時面板使用)
│       └── YYYYMMDD.json       # 歷史每週的大戶籌碼快照
├── scripts/                    # 各式 Python 爬蟲與打包腳本
└── .github/workflows/          # 自動化排程 (CI/CD)
```

## 🤖 自動化排程 (GitHub Actions)

- **`fetch_yahoo.yml` (日常維護)**：週一至週五台灣時間 20:00 (UTC 12:00) 自動執行，更新最新一天的券商/法人/資券紀錄，並於每週五連帶更新集保大戶籌碼。
- **`backfill_yahoo.yml` (歷史回補)**：手動觸發 (workflow_dispatch)，用於一次性回補過去幾個月的 Yahoo 大戶與資券資料。內建每 100 檔自動 Commit 的防中斷機制。

## ⚠️ 免責聲明
本專案為研究與開源交流用途，不提供任何投資建議。抓取之資料皆來自公開網路資訊與證交所/集保中心開放資料。
