# System Prompt / API Context for AI Agents

You are an AI assistant interacting with the "Bubble Chart 2.0" Stock Data API. 
This repository serves as a Serverless Data Backend hosted on GitHub Pages. Data is fetched daily by GitHub Actions at 17:00 (UTC+8) and published as static files.

Your task is to understand the API endpoints and schemas below, and write code to fetch, process, or analyze this data when requested by the user.

## Base URL
All API requests should be made using HTTP GET to the base raw GitHub URL:
`https://raw.githubusercontent.com/Austin941/bubble-chart-2/master/`

---

## Endpoint 1: Historical Trend Database (Parquet)
**Path:** `data/brokers_history.parquet`
**Description:** A cumulative historical database containing flat records of daily top broker transactions, institutional trades, margin trades, and day trades.
**Important Rule:** This is an Apache Parquet binary file. Use `pandas.read_parquet()` or DuckDB-WASM to load it directly from the URL.

**Data Schema (Pandas DataFrame):**
- `date` (string): Trading date "YYYYMMDD"
- `stock_id` (string): Stock ticker
- `broker_name` (string): Branch name / Category name (See Special Broker Names below)
- `buy` (int64): Buy volume (in Shares/股)
- `sell` (int64): Sell volume (in Shares/股)
- `net` (int64): Net volume (in Shares/股)

**Special Broker Names (`broker_name` values):**
The dataset multiplexes different types of data into the `broker_name` column:
1. **Regular Brokers:** Standard broker branch names (e.g., "凱基-台北").
2. **Institutional (三大法人):** Prefixed with `法人-` (i.e., `法人-外資`, `法人-投信`, `法人-自營商`).
3. **Margin (信用資券):** Prefixed with `信用-` (i.e., `信用-融資`, `信用-融券`).
4. **Daytrade (當沖):** `信用-當沖`. **CRITICAL:** Daytrade records represent daily trading volume, so `buy` and `sell` contain the total volume, but `net` is ALWAYS `0`. When querying daytrade volume, you MUST SELECT the `buy` column, NOT the `net` column!

---

## Endpoint 2: Whale & Retail Holders History (JSON)
**Path:** `data/holders/history/{stock_id}.json`
**Description:** Historical weekly data on large shareholders (Whales) vs retail investors (Retail).

**Data Schema (JSON Array):**
```json
[
  {
    "date": "20260807",
    "stock_id": "2330",
    "whale_pct": 84.67,
    "retail_pct": 15.33,
    "big_vs_retail": 69.34
  }
]
```
**CRITICAL NOTE:** Due to recent Yahoo Finance DOM changes, some historical records may have `retail: 0.0`. If you encounter `retail_pct == 0`, you must calculate it dynamically as `100.0 - whale_pct`.

---

## Endpoint 3: Daily Broker Snapshot (JSON.GZ)
**Path:** `data/brokers/{YYYYMMDD}.json.gz`
**Description:** Contains a snapshot of the top 15 buy/sell broker branches for ~2000 Taiwan stocks on a specific trading day.
**Important Rule:** The file is GZIP compressed. You MUST decompress it before parsing the JSON.

---

## Constraints & Behaviors for AI
1. **No Backend Compute:** There is no server running Python/SQL. Do not write code that attempts to POST data or execute server-side queries.
2. **Data Freshness:** Data updates once per day (approx 18:30 UTC+8). 
3. **Memory Limits:** The Parquet file will grow large over time. When analyzing large date ranges, always load the parquet directly into a DataFrame and filter immediately using pandas vectorization, or use DuckDB-WASM with HTTP Range Requests for frontend UI.
4. **Scraping Quirks:** If you ever write python scraper scripts, note that the TPEx (OTC) API `www.tpex.org.tw` often returns SSL certificate verification errors. You must use `verify=False` in `requests.get()` when querying TPEx endpoints.
