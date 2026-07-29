# 泡泡圖 2.0

台股千張大戶、散戶持股分布與分點進出視覺化工具。

## 架構

```
資料流：TDCC / FinMind → GitHub Actions → data/ → Vercel 前端
每次執行只需 2 個 API 請求，不論追蹤幾百支股票
```

## 前置作業

1. 至 [finmindtrade.com](https://finmindtrade.com/) 免費註冊，取得 API Token
2. GitHub repo → Settings → Secrets → Actions → 新增 `FINMIND_TOKEN`
3. 至 [vercel.com](https://vercel.com/) 連接此 repo 自動部署

## 本機測試

```bash
cd scripts
pip install -r requirements.txt

# 設定 Token
export FINMIND_TOKEN="你的Token"   # Windows: set FINMIND_TOKEN=你的Token

# 測試大戶/散戶（不需 Token，TDCC 直接抓）
python fetch_holders.py

# 測試分點資料（需 FinMind Token）
python fetch_brokers.py

# 補抓歷史資料
python backfill.py --from 2024-01-01 --to 2025-07-01 --target both
```

## GitHub Actions 排程

| Workflow | 排程 | 說明 |
|---------|------|------|
| `fetch_holders.yml` | 每週五 18:30 | TDCC 全市場大戶/散戶 |
| `fetch_brokers.yml` | 週一至五 16:45 | FinMind 全市場分點 |
| `backfill.yml` | 手動觸發 | 補抓指定日期範圍 |

## 資料來源

- **集保結算所 TDCC**：股權分散表（免費，每週五）
- **FinMind**：分點買賣 Parquet（免費方案 600次/hr）
- **TWSE OpenAPI**：股票基本資料（免費）
