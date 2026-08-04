"""
泡泡圖 2.0 — 歷史資料補抓工具 (backfill)
一次性或手動觸發，補抓指定日期範圍的歷史資料

用法：
  python backfill.py --from 2024-01-01 --to 2025-07-01
"""
import sys, os, argparse, time, requests
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    FINMIND_DATA_URL, FINMIND_STORAGE_URL,
    DATASET_HOLDERS, DATASET_BROKERS,
    HOLDERS_DIR, BROKERS_DIR,
    WHALE_LEVEL, RETAIL_LEVELS, MID_LEVELS, HOLDER_LEVELS,
    BACKFILL_SLEEP, REQUEST_TIMEOUT,
)
from utils import retry, save_json, already_exists, ts, log

TOKEN = os.environ.get("FINMIND_TOKEN", "")


# ─────────────────────────────────────────────────────────
# 輔助：產生日期序列
# ─────────────────────────────────────────────────────────
def date_range(start: str, end: str, step_days: int = 1):
    """產生從 start 到 end 的日期清單（格式 YYYY-MM-DD）"""
    cur = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    while cur <= end_dt:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=step_days)


def friday_range(start: str, end: str):
    """只產生週五日期（集保資料每週五更新）"""
    for d in date_range(start, end):
        if datetime.strptime(d, "%Y-%m-%d").weekday() == 4:  # 4 = Friday
            yield d


def weekday_range(start: str, end: str):
    """只產生週一至週五"""
    for d in date_range(start, end):
        if datetime.strptime(d, "%Y-%m-%d").weekday() < 5:
            yield d


# ─────────────────────────────────────────────────────────
# 補抓大戶 / 散戶（FinMind 歷史版）
# ─────────────────────────────────────────────────────────
@retry(max_attempts=3, delay=15)
def fetch_holders_finmind(date: str) -> pd.DataFrame:
    """從 FinMind 取得特定日期的股權分散資料（含全市場）"""
    resp = requests.get(
        FINMIND_DATA_URL,
        params={
            "dataset": DATASET_HOLDERS,
            "start_date": date,
            "end_date": date,
        },
        headers={"Authorization": f"Bearer {TOKEN}"},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("data"):
        return pd.DataFrame()
    return pd.DataFrame(body["data"])


def backfill_holders(start: str, end: str):
    log.info(f"📅 補抓大戶資料：{start} ~ {end}（每週五）")
    for date in friday_range(start, end):
        date_str = date.replace("-", "")
        out_path = HOLDERS_DIR / f"{date_str}.json"
        if already_exists(out_path):
            continue
        try:
            df = fetch_holders_finmind(date)
            if df.empty:
                log.warning(f"  {date} 無資料（假日 or 市場未開）")
                time.sleep(BACKFILL_SLEEP)
                continue

            # 整理格式（FinMind 欄位不同於 TDCC CSV）
            stocks = {}
            level_col = next((c for c in ("HoldingSharesLevel", "level", "holding_level") if c in df.columns), None)
            for stock_id, grp in df.groupby("stock_id"):
                sid = str(stock_id).strip().zfill(4)
                levels_dict = {}
                whale_pct = retail_pct = mid_pct = 0.0
                whale_holders = retail_holders = total_holders = 0

                for _, row in grp.iterrows():
                    lv_label = str(row.get(level_col or "HoldingSharesLevel", ""))
                    pct = float(row.get("percent", row.get("pct", 0)))
                    people = int(row.get("people", 0))
                    levels_dict[lv_label] = {"pct": pct, "people": people}
                    # 根據標籤判斷大/散
                    if "1,000,001" in lv_label or "1000001" in lv_label:
                        whale_pct += pct
                        whale_holders += people
                    elif any(x in lv_label for x in ["999", "5,000", "10,000"]):
                        retail_pct += pct
                        retail_holders += people
                    total_holders += people

                stocks[sid] = {
                    "whale_pct": round(whale_pct, 4),
                    "retail_pct": round(retail_pct, 4),
                    "mid_pct": round(max(0, 100 - whale_pct - retail_pct), 4),
                    "big_vs_retail": round(whale_pct - retail_pct, 4),
                    "whale_holders": whale_holders,
                    "retail_holders": retail_holders,
                    "total_holders": total_holders,
                    "levels": levels_dict,
                }

            output = {
                "date": date_str,
                "source": "FinMind",
                "fetched_at": ts(),
                "total_stocks": len(stocks),
                "stocks": stocks,
            }
            save_json(out_path, output)
            log.info(f"  ✅ {date_str}：{len(stocks)} 支股票")

        except Exception as e:
            log.error(f"  ❌ {date}：{e}")

        time.sleep(BACKFILL_SLEEP)


# ─────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="補抓歷史資料")
    parser.add_argument("--from", dest="from_date", required=True, help="開始日期 YYYY-MM-DD")
    parser.add_argument("--to",   dest="to_date",   required=True, help="結束日期 YYYY-MM-DD")
    args = parser.parse_args()

    if not TOKEN:
        log.error("請設定 FINMIND_TOKEN 環境變數")
        sys.exit(1)

    log.info(f"backfill：{args.from_date} ~ {args.to_date}")

    backfill_holders(args.from_date, args.to_date)

    log.info("backfill 全部完成 ✅")


if __name__ == "__main__":
    main()
