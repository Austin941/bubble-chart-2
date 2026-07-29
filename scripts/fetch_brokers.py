"""
泡泡圖 2.0 — 抓取 FinMind 全市場分點買賣資料（日更）
一個 Parquet 請求 → 全市場所有股票的分點進出  極低 API 負載

環境變數：FINMIND_TOKEN（存於 GitHub Secrets）
"""
import sys, os, requests, pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    FINMIND_STORAGE_URL, BROKERS_DIR,
    DATASET_BROKERS, TOP_BROKER_N,
    REQUEST_TIMEOUT, RETRY_ATTEMPTS, RETRY_DELAY,
)
from utils import retry, save_json, already_exists, ts, log

TOKEN = os.environ.get("FINMIND_TOKEN", "")


# ─────────────────────────────────────────────────────────
# 1. 下載 FinMind Parquet（全市場一包）
# ─────────────────────────────────────────────────────────
@retry(max_attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY)
def fetch_parquet_url(date: str) -> str:
    """向 FinMind 取得當日 Parquet 下載連結"""
    if not TOKEN:
        raise EnvironmentError("FINMIND_TOKEN 未設定，請確認 GitHub Secrets")

    log.info(f"⬇  取得 FinMind Parquet 連結：{date}")
    resp = requests.get(
        FINMIND_STORAGE_URL,
        params={"dataset": DATASET_BROKERS, "date": date},
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()

    if not body.get("data"):
        raise ValueError(f"FinMind 無此日資料：{date}（可能假日或資料尚未釋出）")

    url = body["data"][0].get("download_url") or body["data"][0].get("url")
    if not url:
        raise ValueError(f"找不到 download_url，回應：{body}")
    return url


@retry(max_attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY)
def download_parquet(url: str) -> pd.DataFrame:
    """下載 Parquet 並回傳 DataFrame"""
    log.info(f"⬇  下載 Parquet...")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    df = pd.read_parquet(BytesIO(resp.content))
    log.info(f"  Parquet 大小：{resp.headers.get('Content-Length','?')} bytes，共 {len(df)} 筆記錄")
    return df


# ─────────────────────────────────────────────────────────
# 2. 解析分點資料
# ─────────────────────────────────────────────────────────
def process_brokers(df: pd.DataFrame) -> dict:
    """
    將全市場 Parquet 整理成以 stock_id 為 key 的字典。
    每支股票保留前 TOP_BROKER_N 大買超 & 賣超分點。
    """
    # 欄位標準化（FinMind 可能版本不同）
    col_map = {
        "stock_id": ["stock_id", "StockID", "code"],
        "broker_id": ["broker_id", "BrokerID", "broker"],
        "broker_name": ["broker_name", "BrokerName", "broker_nm"],
        "buy": ["buy", "Buy", "buy_vol"],
        "sell": ["sell", "Sell", "sell_vol"],
    }
    for target, candidates in col_map.items():
        for c in candidates:
            if c in df.columns and c != target:
                df = df.rename(columns={c: target})
                break

    # 數值型別
    for col in ("buy", "sell"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    df["net"] = df["buy"] - df["sell"]

    result = {}
    for stock_id, grp in df.groupby("stock_id"):
        sid = str(stock_id).strip().zfill(4)
        try:
            top_buy = (
                grp.nlargest(TOP_BROKER_N, "buy")
                [["broker_id", "broker_name", "buy", "sell", "net"]]
                .to_dict("records")
            )
            top_sell = (
                grp.nsmallest(TOP_BROKER_N, "net")
                [["broker_id", "broker_name", "buy", "sell", "net"]]
                .to_dict("records")
            )
            result[sid] = {
                "top_buy":  top_buy,
                "top_sell": top_sell,
                "summary": {
                    "total_buy":    int(grp["buy"].sum()),
                    "total_sell":   int(grp["sell"].sum()),
                    "net":          int(grp["net"].sum()),
                    "broker_count": len(grp),
                },
            }
        except Exception as e:
            log.warning(f"  跳過 {sid}：{e}")

    return result


# ─────────────────────────────────────────────────────────
# 3. 主程式
# ─────────────────────────────────────────────────────────
def main():
    log.info("═" * 50)
    log.info("fetch_brokers  開始執行")

    # 使用前一個交易日（盤後才有資料）
    target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    date_str = target_date.replace("-", "")

    out_path = BROKERS_DIR / f"{date_str}.json"
    if already_exists(out_path):
        return

    try:
        url = fetch_parquet_url(target_date)
        df = download_parquet(url)
    except ValueError as e:
        log.warning(f"FinMind 無資料（{e}），跳過")
        return

    log.info(f"  解析 {df['stock_id'].nunique() if 'stock_id' in df.columns else '?'} 支股票的分點資料...")
    stocks = process_brokers(df)

    output = {
        "date":         date_str,
        "source":       "FinMind",
        "fetched_at":   ts(),
        "total_stocks": len(stocks),
        "stocks":       stocks,
    }
    save_json(out_path, output)
    log.info(f"fetch_brokers  完成：{len(stocks)} 支股票")


if __name__ == "__main__":
    main()
