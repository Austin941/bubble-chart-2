"""
泡泡圖 2.0 — 抓取 TWSE 股票基本資料（名稱、產業分類）
快取在 data/meta/stocks.json，每月更新一次即可
"""
import sys, requests, json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import META_DIR, TWSE_OPENAPI_BASE, REQUEST_TIMEOUT
from utils import retry, save_json, get_request_headers, ts, log

META_PATH = META_DIR / "stocks.json"
TWSE_LISTED = f"{TWSE_OPENAPI_BASE}/exchangeReport/STOCK_DAY_AVG_ALL"
TWSE_INDUSTRY = f"{TWSE_OPENAPI_BASE}/exchangeReport/BWIBBU_d"


@retry(max_attempts=3, delay=10)
def fetch_stock_list() -> list:
    """從 TWSE OpenAPI 取得上市股票清單"""
    log.info("⬇  下載 TWSE 股票清單...")
    resp = requests.get(TWSE_LISTED, timeout=REQUEST_TIMEOUT, headers=get_request_headers())
    resp.raise_for_status()
    return resp.json()


def main():
    log.info("fetch_meta  開始執行")

    # 如果快取還新鮮（30天內），直接跳過
    if META_PATH.exists():
        cached = json.loads(META_PATH.read_text(encoding="utf-8"))
        fetched = cached.get("fetched_at", "")[:10]
        days_old = (datetime.now() - datetime.fromisoformat(fetched)).days if fetched else 999
        if days_old < 30:
            log.info(f"⏭  股票清單快取仍有效（{days_old} 天前），跳過")
            return

    data = fetch_stock_list()

    stocks = {}
    for row in data:
        sid = str(row.get("Code", "")).strip()
        if not sid:
            continue
        stocks[sid] = {
            "name":     row.get("Name", "").strip(),
            "industry": row.get("IndustryType", "").strip(),
            "market":   "上市",
        }

    output = {
        "fetched_at": ts(),
        "total":      len(stocks),
        "stocks":     stocks,
    }
    save_json(META_PATH, output)
    log.info(f"fetch_meta  完成：{len(stocks)} 支股票")


if __name__ == "__main__":
    main()
