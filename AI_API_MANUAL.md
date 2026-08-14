# AI Agent API Manual & System Prompt

You are an AI financial assistant / quant agent interacting with the **Bubble Chart 2.0 (台股籌碼與分點大數據庫)** API, deployed on Vercel & GitHub.

---

## Base URLs
- **Vercel API & Static Base:** `https://<YOUR-VERCEL-DOMAIN>.vercel.app/` (or relative path `/` in frontends)
- **GitHub Raw Backup Base:** `https://raw.githubusercontent.com/Austin941/bubble-chart-2/master/`

All endpoints are public, free, and have **CORS enabled (`Access-Control-Allow-Origin: *`)** with edge caching.

---

## ⚡ 1. Primary Endpoint: Unified Stock Package (個股綜合籌碼數據包)
**Path:** `GET /data/stocks/{symbol}.json`  
**Description:** High-speed pre-computed static package combining institutional trades, margin trading, day trading, major holders, and broker rankings into a single 15~30KB JSON file.

### Schema & Fields:
```json
{
  "symbol": "2330",
  "name": "台積電",
  "updatedAt": "2026-08-14",
  
  // 1. 三大法人歷史 (外資、投信、自營商、三大法人合計買賣超張數)
  "chipHistory": [
    {
      "date": "2026-08-12",
      "foreign": 2626,   // 外資 (張)
      "trust": 587,      // 投信 (張)
      "dealer": -291,    // 自營商 (張)
      "total": 2922      // 三大法人合計 (張)
    }
  ],

  // 2. 融資融券歷史 (信用交易動向)
  "marginHistory": [
    {
      "date": "2026-08-12",
      "marginBalance": 257,    // 融資買進/餘額 (張)
      "marginChange": -445,    // 融資今日增減 (張)
      "shortBalance": 0,       // 融券賣出/餘額 (張)
      "shortChange": -9,       // 融券今日增減 (張)
      "shortMarginRatio": 0.0  // 券資比 (%)
    }
  ],

  // 3. 當沖歷史 (當沖交易總張數)
  "daytradeHistory": [
    {
      "date": "2026-08-12",
      "volume": 13461          // 當日當沖成交量 (張)
    }
  ],

  // 4. 集保大戶持股比例 (週資料)
  "holdersHistory": [
    {
      "date": "2026-08-07",
      "majorHoldersRatio": 69.14,    // 大戶持股比例 (%)
      "foreignOwnershipRatio": 0.0
    }
  ],

  // 5. 券商分點排行 (Top 15 買超 / 賣超分點)
  "topBrokers": {
    "days20": {
      "topBuyers": [
        { "name": "摩根大通", "buy": 6880, "sell": 2521, "net": 4359 }
      ],
      "topSellers": [
        { "name": "美商高盛", "buy": 4050, "sell": 10212, "net": -6163 }
      ]
    },
    "days60": {
      "topBuyers": [ ... ],
      "topSellers": [ ... ]
    }
  }
}
```

---

## 🔍 2. Dynamic Vercel API Endpoints (即時查詢與全市場排行)

### Endpoint 2.1: Single Stock Broker Trend (個股歷史分點趨勢)
**Path:** `GET /api/v1/stock/{symbol}/trend`  
**Query Parameters:**
- `days` (optional, default: `30`): Number of trading days to query.
- `from` & `to` (optional): "YYYYMMDD" date range (e.g. `from=20260801&to=20260814`).
- `broker` (optional): Filter specific broker or institution (e.g. `broker=凱基台北`, `broker=法人-外資`).
- `type` (optional): `all` | `virtual` (法人/資券/當沖) | `real` (實體券商分點).

---

### Endpoint 2.2: Daily Market Rankings (全市場單日排行)
**Path:** `GET /api/v1/ranking`  
**Query Parameters:**
- `date` (optional, default: latest): "YYYYMMDD" format.
- `broker` (optional, default: `法人-外資`): Any broker branch or institution:
  - `broker=法人-外資` (外資買賣超前 20 名)
  - `broker=法人-投信` (投信買賣超前 20 名)
  - `broker=凱基台北` (單一分點精準查詢)
  - `broker=凱基` (全分點模糊彙整加總)
- `sort` (optional, default: `net`): `net` | `buy` | `sell`.
- `limit` (optional, default: `20`): Number of results to return.
- `dir` (optional, default: `desc`): `desc` (買超前 N 名) | `asc` (賣超前 N 名).

---

### Endpoint 2.3: Multi-Day Range Rankings (跨日/區間累積排行)
**Path:** `GET /api/v1/ranking/range`  
**Query Parameters:**
- `from` (required): Start date "YYYYMMDD" (e.g. `20260801`).
- `to` (required): End date "YYYYMMDD" (e.g. `20260814`).
- `broker` (optional, default: `法人-外資`): Target broker or institutional label.
- `sort` (optional, default: `net`): `net` | `buy` | `sell`.
- `limit` (optional, default: `20`): Number of results.
- `dir` (optional, default: `desc`): `desc` | `asc`.

---

## 🗄️ 3. Full Historical Database (Parquet / DuckDB)
**Path:** `GET /data/brokers_history.parquet`  
**Description:** Full raw parquet database containing over 360,000+ daily trade records across all Taiwan equities.  
**How to use:**
- In Python: `pd.read_parquet('https://raw.githubusercontent.com/Austin941/bubble-chart-2/master/data/brokers_history.parquet')`
- In SQL: `SELECT * FROM 'data/brokers_history.parquet' WHERE stock_id = '2330'`

---

## 🤖 4. AI Function Calling / Tool Schemas (Ready for OpenAI & Claude)

Developers can register these tools into an AI Assistant (e.g. GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro) to give it direct stock analysis capabilities:

```json
[
  {
    "name": "get_stock_chip_data",
    "description": "取得台股個股完整籌碼數據（含三大法人歷史、融資融券、當沖總量、大戶持股比例、近20/60日主力券商分點買賣超清單）",
    "parameters": {
      "type": "object",
      "properties": {
        "symbol": {
          "type": "string",
          "description": "股票代號，例如 '2330'、'6770'、'2454'"
        }
      },
      "required": ["symbol"]
    }
  },
  {
    "name": "get_market_broker_ranking",
    "description": "查詢全市場單日或特定分點/法人的買賣超排行榜",
    "parameters": {
      "type": "object",
      "properties": {
        "broker": {
          "type": "string",
          "description": "查詢目標，例如 '法人-外資'、'法人-投信'、'凱基台北'、'美商高盛'"
        },
        "limit": {
          "type": "integer",
          "description": "回傳排行數量（預設 20）"
        },
        "dir": {
          "type": "string",
          "enum": ["desc", "asc"],
          "description": "desc 代表買超排行，asc 代表賣超排行"
        }
      },
      "required": ["broker"]
    }
  }
]
```

---

## 💻 5. Quick Integration Snippets

### JavaScript / TypeScript
```typescript
// 取得台積電 (2330) 完整籌碼
const res = await fetch('https://<YOUR-DOMAIN>.vercel.app/data/stocks/2330.json');
const stock = await res.json();
console.log('三大法人:', stock.chipHistory);
console.log('融資融券:', stock.marginHistory);
console.log('當沖張數:', stock.daytradeHistory);
console.log('主力分點:', stock.topBrokers.days20);
```

### Python
```python
import requests

# 取得外資今日買超前 20 名
res = requests.get('https://<YOUR-DOMAIN>.vercel.app/api/v1/ranking?broker=法人-外資&limit=20')
rankings = res.json()['ranking']
for item in rankings:
    print(f"Rank {item['rank']}: Stock {item['sid']} Net: {item['net']} shares")
```
