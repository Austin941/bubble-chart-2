"""
泡泡圖 2.0 — 抓取 TDCC 股權分散表（大戶 / 散戶）
資料來源：smart.tdcc.com.tw  每週五更新
一個請求 → 全市場所有股票  極低 API 負載
"""
import sys, requests, pandas as pd
from io import StringIO
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    TDCC_CSV_URL, HOLDERS_DIR,
    WHALE_LEVEL, RETAIL_LEVELS, MID_LEVELS,
    HOLDER_LEVELS, REQUEST_TIMEOUT, RETRY_ATTEMPTS, RETRY_DELAY,
)
from utils import retry, save_json, already_exists, get_request_headers, ts, log


# ─────────────────────────────────────────────────────────
# 1. 下載 TDCC CSV
# ─────────────────────────────────────────────────────────
@retry(max_attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY)
def fetch_tdcc_csv() -> pd.DataFrame:
    """
    一次下載全市場所有股票的股權分散 CSV。
    回傳欄位：資料日期, 證券代號, 持股分級, 人數, 股數, 占集保庫存數比例%
    """
    log.info(f"⬇  下載 TDCC CSV：{TDCC_CSV_URL}")
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    resp = requests.get(
        TDCC_CSV_URL,
        timeout=REQUEST_TIMEOUT,
        headers=get_request_headers(),
        verify=False,
    )
    resp.raise_for_status()
    resp.encoding = "utf-8-sig"   # 處理 BOM

    df = pd.read_csv(StringIO(resp.text))
    df.columns = df.columns.str.strip()

    # 標準化欄名（TDCC 偶爾調整欄位名）
    rename_map = {
        "資料日期": "date",
        "證券代號": "stock_id",
        "持股分級": "level",
        "人數": "people",
        "股數": "shares",
        "占集保庫存數比例%": "pct",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df["stock_id"] = df["stock_id"].astype(str).str.strip().str.zfill(4)
    df["level"] = pd.to_numeric(df["level"], errors="coerce")
    df["pct"] = pd.to_numeric(df["pct"], errors="coerce").fillna(0.0)
    df["people"] = pd.to_numeric(df["people"], errors="coerce").fillna(0).astype(int)
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce").fillna(0).astype(int)

    log.info(f"  TDCC CSV：{len(df)} 筆，涵蓋 {df['stock_id'].nunique()} 支股票")
    return df


# ─────────────────────────────────────────────────────────
# 2. 解析 & 計算各股票的大戶 / 散戶比例
# ─────────────────────────────────────────────────────────
def process_stock(group: pd.DataFrame) -> dict:
    """對單一股票的 DataFrame 計算大戶/散戶比例"""
    levels_dict = {}
    for _, row in group.iterrows():
        lv = int(row["level"])
        levels_dict[str(lv)] = {
            "label": HOLDER_LEVELS.get(lv, f"Level {lv}"),
            "people": int(row["people"]),
            "shares": int(row["shares"]),
            "pct": round(float(row["pct"]), 4),
        }

    whale_rows  = group[group["level"] == WHALE_LEVEL]
    retail_rows = group[group["level"].isin(RETAIL_LEVELS)]
    mid_rows    = group[group["level"].isin(MID_LEVELS)]

    whale_pct  = round(float(whale_rows["pct"].sum()), 4)
    retail_pct = round(float(retail_rows["pct"].sum()), 4)
    mid_pct    = round(float(mid_rows["pct"].sum()), 4)

    return {
        "whale_pct":      whale_pct,
        "retail_pct":     retail_pct,
        "mid_pct":        mid_pct,
        "big_vs_retail":  round(whale_pct - retail_pct, 4),   # 正值 = 大戶主導
        "whale_holders":  int(whale_rows["people"].sum()),
        "retail_holders": int(retail_rows["people"].sum()),
        "total_holders":  int(group["people"].sum()),
        "total_shares":   int(group["shares"].sum()),
        "levels":         levels_dict,
    }


def process_all(df: pd.DataFrame) -> dict:
    """處理全市場 DataFrame，回傳以 stock_id 為 key 的字典"""
    result = {}
    for stock_id, grp in df.groupby("stock_id"):
        try:
            result[stock_id] = process_stock(grp)
        except Exception as e:
            log.warning(f"  跳過 {stock_id}：{e}")
    return result


# ─────────────────────────────────────────────────────────
# 3. 主程式
# ─────────────────────────────────────────────────────────
def main():
    log.info("═" * 50)
    log.info("fetch_holders  開始執行")

    df = fetch_tdcc_csv()

    # 取得資料日期（TDCC CSV 第一欄）
    raw_date = str(df["date"].iloc[0]) if "date" in df.columns else datetime.now().strftime("%Y%m%d")
    # 格式可能是 "1130718"（民國）或 "20250718"（西元），統一轉西元
    if len(raw_date) == 7 and raw_date.isdigit():
        ry = int(raw_date[:3]) + 1911
        raw_date = f"{ry}{raw_date[3:]}"
    date_str = raw_date.replace("-", "")

    out_path = HOLDERS_DIR / f"{date_str}.json"
    if already_exists(out_path):
        return

    stocks = process_all(df)

    output = {
        "date":         date_str,
        "source":       "TDCC",
        "fetched_at":   ts(),
        "total_stocks": len(stocks),
        "stocks":       stocks,
    }

    save_json(out_path, output)
    save_json(HOLDERS_DIR / "latest_holders.json", output)
    log.info(f"fetch_holders  完成：{len(stocks)} 支股票")


if __name__ == "__main__":
    main()
