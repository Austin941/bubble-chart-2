# AI Agent SOP: 泡泡圖 2.0 — Vercel API Layer 升級

## 任務定義

你是負責升級「泡泡圖 2.0」(Austin941/bubble-chart-2) 資料供應架構的 AI Agent。
本次任務的目標是新增一個輕量的 Vercel API 代理層，讓前端不再需要在瀏覽器內跑 DuckDB-WASM。

---

## 鐵律（執行前必讀）

1. **禁止刪除任何現有資料檔案**：`data/brokers_history.parquet`、`data/brokers/*.json.gz`、`data/holders/**` 一律不准動。
2. **禁止修改現有爬蟲邏輯**：`fetch_yahoo_brokers.py` 的爬蟲部分（`fetch_yahoo_stock`, `fetch_t86_data`）禁止修改，只能在 `main()` 函數末尾追加新輸出邏輯。
3. **禁止破壞泡泡圖主頁**：`index.html` 和 `src/bubble-chart.js` 不在本次任務範圍內，禁止修改。
4. **DuckDB-WASM 必須保留**：`simple_history.html` 裡的 DuckDB 邏輯不能刪除，只能改成「優先打 API，失敗才用 DuckDB」。
5. **CORS 全開**：所有 API 函數必須在 response header 加入 `Access-Control-Allow-Origin: *`。

---

## 工作目錄結構（執行後應長這樣）

```
bubble-chart-2/
  api/                          ← [新增] Vercel API 函數
    v1/
      stock/
        [sid]/
          trend.js              ← System A：單股券商歷史
          holders.js            ← System C：持股結構
      ranking/
        index.js                ← System B1：單日排行
        range.js                ← System B2：區間排行（分層）
    _lib/
      fetch-github.js           ← GitHub Raw 抓取工具
      decompress.js             ← .json.gz 解壓縮工具
      cors.js                   ← CORS header 工具
      cache.js                  ← Cache-Control 計算工具
  data/
    brokers/
      history/                  ← [新增] 個股券商歷史 JSON
        2330.json
        2454.json
        ...（全部股票）
      agg/                      ← [新增] 預計算彙整
        weekly/
          2026-W33.json
        monthly/
          202608.json
    brokers_history.parquet     ← [不動]
    brokers/20260814.json.gz    ← [不動]
    holders/history/2330.json   ← [不動]
  scripts/
    fetch_yahoo_brokers.py      ← [修改] 末尾追加輸出邏輯
  src/
    data-loader.js              ← [修改] 加入降級邏輯
  simple_history.html           ← [修改] 改用 API，保留 DuckDB 備援
  vercel.json                   ← [修改] 加入 Cache Header
```

---

## 第一階段：修改 Python 腳本（資料切分）

**檔案**：`scripts/fetch_yahoo_brokers.py`

在 `main()` 函數的最末尾（`df.to_parquet(...)` 之後），追加以下三段輸出邏輯：

### Step 1-A：輸出個股歷史 JSON

```python
# === 新增：輸出個股歷史 JSON (data/brokers/history/{sid}.json) ===
print("Generating per-stock history JSON...")
history_dir = Path(config.DATA_DIR) / 'brokers' / 'history'
history_dir.mkdir(parents=True, exist_ok=True)

# 讀取完整 Parquet（含今日剛追加的資料）
full_df = pd.read_parquet(history_file)

for sid, group in full_df.groupby('stock_id'):
    sid_records = []
    for date_val, date_group in group.groupby('date', sort=False):
        brokers_list = []
        for _, row in date_group.iterrows():
            brokers_list.append({
                "name": row['broker_name'],
                "buy": int(row['buy']),
                "sell": int(row['sell']),
                "net": int(row['net'])
            })
        sid_records.append({
            "date": date_val,
            "brokers": brokers_list
        })
    # 按日期倒序排列
    sid_records.sort(key=lambda x: x['date'], reverse=True)
    out_path = history_dir / f"{sid}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(sid_records, f, ensure_ascii=False, separators=(',', ':'))

print(f"Generated {full_df['stock_id'].nunique()} per-stock history JSON files.")
```

### Step 1-B：輸出週彙整 JSON

```python
# === 新增：輸出週彙整 JSON (data/brokers/agg/weekly/YYYY-Www.json) ===
weekly_dir = Path(config.DATA_DIR) / 'brokers' / 'agg' / 'weekly'
weekly_dir.mkdir(parents=True, exist_ok=True)

full_df['date_parsed'] = pd.to_datetime(full_df['date'], format='%Y%m%d')
full_df['week_key'] = full_df['date_parsed'].dt.strftime('%G-W%V')

for week_key, week_group in full_df.groupby('week_key'):
    stocks_agg = {}
    for sid, sid_group in week_group.groupby('stock_id'):
        broker_agg = []
        for broker_name, b_group in sid_group.groupby('broker_name'):
            broker_agg.append({
                "name": broker_name,
                "buy": int(b_group['buy'].sum()),
                "sell": int(b_group['sell'].sum()),
                "net": int(b_group['net'].sum())
            })
        stocks_agg[sid] = broker_agg
    week_dates = sorted(week_group['date'].unique())
    out = {
        "period": week_key,
        "from": week_dates[0],
        "to": week_dates[-1],
        "stocks": stocks_agg
    }
    out_path = weekly_dir / f"{week_key}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

print("Generated weekly aggregation JSON files.")
```

### Step 1-C：輸出月彙整 JSON

```python
# === 新增：輸出月彙整 JSON (data/brokers/agg/monthly/YYYYMM.json) ===
monthly_dir = Path(config.DATA_DIR) / 'brokers' / 'agg' / 'monthly'
monthly_dir.mkdir(parents=True, exist_ok=True)

full_df['month_key'] = full_df['date'].str[:6]  # '202608'

for month_key, month_group in full_df.groupby('month_key'):
    stocks_agg = {}
    for sid, sid_group in month_group.groupby('stock_id'):
        broker_agg = []
        for broker_name, b_group in sid_group.groupby('broker_name'):
            broker_agg.append({
                "name": broker_name,
                "buy": int(b_group['buy'].sum()),
                "sell": int(b_group['sell'].sum()),
                "net": int(b_group['net'].sum())
            })
        stocks_agg[sid] = broker_agg
    month_dates = sorted(month_group['date'].unique())
    out = {
        "period": month_key,
        "from": month_dates[0],
        "to": month_dates[-1],
        "stocks": stocks_agg
    }
    out_path = monthly_dir / f"{month_key}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))

print("Generated monthly aggregation JSON files.")
```

---

## 第二階段：新增 Vercel API 函數

### Step 2-A：工具函數

**新增 `api/_lib/cors.js`**：
```javascript
export function setCors(res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
}
```

**新增 `api/_lib/cache.js`**：
```javascript
export function setCacheHeader(res, dateStr) {
  const today = new Date().toISOString().slice(0,10).replace(/-/g,'');
  if (dateStr && dateStr < today) {
    res.setHeader('Cache-Control', 'public, s-maxage=86400, stale-while-revalidate=604800');
  } else {
    res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=60');
  }
}
```

**新增 `api/_lib/fetch-github.js`**：
```javascript
const BASE = 'https://raw.githubusercontent.com/Austin941/bubble-chart-2/master/';

export async function fetchGithubJson(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GitHub fetch failed: ${path} (${res.status})`);
  return res.json();
}

export async function fetchGithubGz(path) {
  const { ungzip } = await import('node-gzip');
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`GitHub fetch failed: ${path} (${res.status})`);
  const buf = Buffer.from(await res.arrayBuffer());
  const decompressed = await ungzip(buf);
  return JSON.parse(decompressed.toString('utf-8'));
}
```

### Step 2-B：System A — 單股趨勢

**新增 `api/v1/stock/[sid]/trend.js`**：
```javascript
import { setCors } from '../../../_lib/cors.js';
import { setCacheHeader } from '../../../_lib/cache.js';
import { fetchGithubJson } from '../../../_lib/fetch-github.js';

export default async function handler(req, res) {
  setCors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();

  const { sid } = req.query;
  const { days = '30', from, to, broker, type = 'all' } = req.query;

  try {
    const data = await fetchGithubJson(`data/brokers/history/${sid}.json`);

    let filtered = data;
    if (from && to) {
      filtered = data.filter(d => d.date >= from && d.date <= to);
    } else {
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - parseInt(days));
      const cutoffStr = cutoff.toISOString().slice(0,10).replace(/-/g,'');
      filtered = data.filter(d => d.date >= cutoffStr);
    }

    const result = {};
    for (const dayData of filtered) {
      for (const b of dayData.brokers) {
        const isVirtual = b.name.startsWith('法人-') || b.name.startsWith('信用-');
        if (type === 'virtual' && !isVirtual) continue;
        if (type === 'real' && isVirtual) continue;
        if (broker && !b.name.includes(broker)) continue;

        if (!result[b.name]) result[b.name] = [];
        result[b.name].push({ date: dayData.date, buy: b.buy, sell: b.sell, net: b.net });
      }
    }

    setCacheHeader(res, filtered[0]?.date);
    return res.json({ sid, range: { from: filtered.at(-1)?.date, to: filtered[0]?.date }, brokers: result });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
```

### Step 2-C：System B1 — 單日排行

**新增 `api/v1/ranking/index.js`**：
```javascript
import { setCors } from '../../_lib/cors.js';
import { setCacheHeader } from '../../_lib/cache.js';
import { fetchGithubGz } from '../../_lib/fetch-github.js';

export default async function handler(req, res) {
  setCors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();

  const { date, broker = '法人-外資', sort = 'net', limit = '20', dir = 'desc' } = req.query;
  const targetDate = date || new Date().toISOString().slice(0,10).replace(/-/g,'');

  try {
    const data = await fetchGithubGz(`data/brokers/${targetDate}.json.gz`);

    const ranking = [];
    for (const [sid, stockData] of Object.entries(data.stocks)) {
      const allBrokers = [...(stockData.top_buy || []), ...(stockData.top_sell || [])];
      const matched = allBrokers.filter(b => b.broker_name.includes(broker));
      if (matched.length === 0) continue;

      const seen = new Set();
      let totalBuy = 0, totalSell = 0, totalNet = 0;
      const matchedLabels = [];
      for (const b of matched) {
        if (!seen.has(b.broker_name)) {
          seen.add(b.broker_name);
          matchedLabels.push(b.broker_name);
          totalBuy += b.buy; totalSell += b.sell; totalNet += b.net;
        }
      }
      ranking.push({ sid, buy: totalBuy, sell: totalSell, net: totalNet, matched_labels: matchedLabels });
    }

    const sortKey = sort === 'buy' ? 'buy' : sort === 'sell' ? 'sell' : 'net';
    ranking.sort((a, b) => dir === 'asc' ? a[sortKey] - b[sortKey] : b[sortKey] - a[sortKey]);
    const top = ranking.slice(0, parseInt(limit)).map((r, i) => ({ rank: i+1, ...r }));

    setCacheHeader(res, targetDate);
    return res.json({ date: targetDate, broker_query: broker, ranking: top });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
```

### Step 2-D：System B2 — 區間排行（分層策略）

**新增 `api/v1/ranking/range.js`**：
```javascript
import { setCors } from '../../_lib/cors.js';
import { setCacheHeader } from '../../_lib/cache.js';
import { fetchGithubJson, fetchGithubGz } from '../../_lib/fetch-github.js';

function getWeekKey(d) {
  // ISO week string: YYYY-Www
  const date = new Date(d);
  const thursday = new Date(date);
  thursday.setDate(date.getDate() - ((date.getDay() + 6) % 7) + 3);
  const year = thursday.getFullYear();
  const week = Math.ceil(((thursday - new Date(year, 0, 1)) / 86400000 + 1) / 7);
  return `${year}-W${String(week).padStart(2,'0')}`;
}

function dateRange(from, to) {
  const dates = [];
  for (let d = new Date(from.slice(0,4)+'-'+from.slice(4,6)+'-'+from.slice(6,8)); 
       d <= new Date(to.slice(0,4)+'-'+to.slice(4,6)+'-'+to.slice(6,8)); 
       d.setDate(d.getDate()+1)) {
    dates.push(d.toISOString().slice(0,10).replace(/-/g,''));
  }
  return dates;
}

function aggregateByBroker(allRecords, broker) {
  // allRecords: [{sid, name, buy, sell, net}]
  const map = {};
  for (const r of allRecords) {
    if (!r.name.includes(broker)) continue;
    if (!map[r.sid]) map[r.sid] = { sid: r.sid, buy: 0, sell: 0, net: 0, matched_labels: new Set() };
    map[r.sid].buy += r.buy;
    map[r.sid].sell += r.sell;
    map[r.sid].net += r.net;
    map[r.sid].matched_labels.add(r.name);
  }
  return Object.values(map).map(v => ({ ...v, matched_labels: [...v.matched_labels] }));
}

export default async function handler(req, res) {
  setCors(res);
  if (req.method === 'OPTIONS') return res.status(200).end();

  const { from, to, broker = '法人-外資', sort = 'net', limit = '20', dir = 'desc' } = req.query;
  if (!from || !to) return res.status(400).json({ error: 'from and to are required' });

  try {
    const dates = dateRange(from, to);
    const diffDays = dates.length;
    let allRecords = [];

    if (diffDays > 90) {
      // 讀月彙整
      const months = [...new Set(dates.map(d => d.slice(0,6)))];
      const files = await Promise.all(months.map(m => fetchGithubJson(`data/brokers/agg/monthly/${m}.json`).catch(() => null)));
      for (const file of files.filter(Boolean)) {
        for (const [sid, brokers] of Object.entries(file.stocks)) {
          for (const b of brokers) allRecords.push({ sid, ...b });
        }
      }
    } else if (diffDays > 22) {
      // 讀週彙整
      const weeks = [...new Set(dates.map(d => getWeekKey(d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6,8))))];
      const files = await Promise.all(weeks.map(w => fetchGithubJson(`data/brokers/agg/weekly/${w}.json`).catch(() => null)));
      for (const file of files.filter(Boolean)) {
        for (const [sid, brokers] of Object.entries(file.stocks)) {
          for (const b of brokers) allRecords.push({ sid, ...b });
        }
      }
    } else {
      // 直接並行抓每日 .json.gz
      const files = await Promise.all(dates.map(d => fetchGithubGz(`data/brokers/${d}.json.gz`).catch(() => null)));
      for (const file of files.filter(Boolean)) {
        for (const [sid, stockData] of Object.entries(file.stocks)) {
          const all = [...(stockData.top_buy||[]), ...(stockData.top_sell||[])];
          for (const b of all) allRecords.push({ sid, name: b.broker_name, buy: b.buy, sell: b.sell, net: b.net });
        }
      }
    }

    const ranking = aggregateByBroker(allRecords, broker);
    const sortKey = sort === 'buy' ? 'buy' : sort === 'sell' ? 'sell' : 'net';
    ranking.sort((a, b) => dir === 'asc' ? a[sortKey] - b[sortKey] : b[sortKey] - a[sortKey]);
    const top = ranking.slice(0, parseInt(limit)).map((r, i) => ({ rank: i+1, ...r }));

    setCacheHeader(res, to);
    return res.json({ from, to, broker_query: broker, ranking: top });
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
```

---

## 第三階段：前端改動

### Step 3-A：`src/data-loader.js` 加入降級邏輯

在現有 DuckDB 查詢函數外層包裝降級邏輯：

```javascript
// 改動：fetchStockTrend 優先打 API，失敗降級 DuckDB
export async function fetchStockTrend(sid, days = 30) {
  try {
    const res = await fetch(`/api/v1/stock/${sid}/trend?days=${days}`, {
      signal: AbortSignal.timeout(5000)
    });
    if (!res.ok) throw new Error('API unavailable');
    return { source: 'api', data: await res.json() };
  } catch (e) {
    console.warn('[Fallback] DuckDB-WASM:', e.message);
    return { source: 'duckdb', data: await fetchStockTrendViaDuckDB(sid, days) };
  }
}
// 原有 DuckDB 邏輯改名為 fetchStockTrendViaDuckDB，邏輯不改
```

### Step 3-B：`vercel.json` 更新

```json
{
  "cleanUrls": true,
  "headers": [
    {
      "source": "/api/(.*)",
      "headers": [
        { "key": "Access-Control-Allow-Origin", "value": "*" }
      ]
    },
    {
      "source": "/data/brokers/history/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, s-maxage=86400, stale-while-revalidate=604800" }
      ]
    },
    {
      "source": "/data/brokers/agg/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, s-maxage=3600, stale-while-revalidate=86400" }
      ]
    },
    {
      "source": "/data/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "public, max-age=604800, immutable" }
      ]
    }
  ]
}
```

---

## 第四階段：驗證清單

- [ ] `data/brokers/history/2330.json` 存在，且內容含真實券商資料
- [ ] `data/brokers/agg/weekly/` 有對應本週的 JSON
- [ ] `data/brokers/agg/monthly/` 有對應本月的 JSON
- [ ] `GET /api/v1/stock/2330/trend?days=7` 回傳 `brokers` 欄位非空
- [ ] `GET /api/v1/ranking?date=20260812&broker=法人-外資&limit=5` 回傳正確排名
- [ ] `GET /api/v1/ranking?date=20260812&broker=凱基台北&limit=5` 只匹配「凱基台北」單點
- [ ] `GET /api/v1/ranking?date=20260812&broker=凱基&limit=5` 所有凱基分點加總
- [ ] `GET /api/v1/ranking/range?from=20260804&to=20260812&broker=法人-外資&limit=5` 正確
- [ ] 前端 API 失敗後自動降級為 DuckDB-WASM（測試方法：把 API URL 暫時改錯）
- [ ] `data/brokers_history.parquet` 仍存在且大小不變
- [ ] `index.html` 泡泡圖功能正常

---

## Git Commit 規範

```
feat(data): generate per-stock history JSON and weekly/monthly aggregations in Python script
feat(api): add Vercel API layer — System A trend + System B ranking endpoints
feat(frontend): API-first with DuckDB-WASM fallback in data-loader.js
chore(vercel): update Cache-Control headers for new static asset paths
```
