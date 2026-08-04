import os
import sys
import argparse
from pathlib import Path
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from utils import log, today_str

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=today_str(), help="要合併的日期 (預設為今日 YYYYMMDD)")
    args = parser.parse_args()

    target_date = args.date
    log.info(f"開始合併 {target_date} 的暫存檔...")

    parquet_files = list(config.BRANCHES_DIR.glob(f"chunk_*_{target_date}.parquet"))
    if not parquet_files:
        log.warning(f"找不到任何符合 {target_date} 的 chunk 檔案。")
        return

    all_dfs = []
    for f in parquet_files:
        try:
            df = pd.read_parquet(f, engine="pyarrow")
            if not df.empty:
                all_dfs.append(df)
            log.info(f"讀取 {f.name} ({len(df)} 筆)")
        except Exception as e:
            log.error(f"讀取 {f.name} 失敗: {e}")

    if not all_dfs:
        log.warning("所有暫存檔皆無資料。")
        return

    merged_df = pd.concat(all_dfs, ignore_index=True)
    
    # 依照 StockID 排序
    merged_df.sort_values(by=["StockID", "BrokerID", "Price"], inplace=True)

    # 輸出最終的大檔
    out_file = config.BRANCHES_DIR / f"branches_{target_date}.parquet"
    merged_df.to_parquet(out_file, index=False, engine="pyarrow", compression="snappy")
    log.info(f"✅ 合併完成！總筆數: {len(merged_df)}，已儲存至 {out_file}")
    
    # 產生一份 CSV 供參考 (可選，但為了節省空間，在 GitHub Actions 可能只要 parquet)
    # merged_df.to_csv(config.BRANCHES_DIR / f"branches_{target_date}.csv", index=False)

    # 清除暫存檔
    log.info("開始清除暫存檔...")
    for f in parquet_files:
        try:
            f.unlink()
        except Exception as e:
            log.warning(f"無法刪除 {f.name}: {e}")

if __name__ == "__main__":
    main()
