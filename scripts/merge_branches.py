import os
import sys
import argparse
import json
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
    
    # 產生輕量化 JSON 給前端使用
    log.info("產生前端用的輕量化 JSON...")
    df = merged_df.copy()
    df['NetVolume'] = df['BuyVolume'] - df['SellVolume']
    df = df[df['NetVolume'] != 0]
    df = df.rename(columns={'BrokerID': 'broker_id', 'BrokerName': 'broker_name', 'BuyVolume': 'buy', 'SellVolume': 'sell', 'NetVolume': 'net'})
    
    def get_top_brokers(g):
        sorted_g = g.sort_values('net', ascending=False)
        buy_list = sorted_g.head(20)[['broker_id', 'broker_name', 'buy', 'sell', 'net']].to_dict('records')
        sell_list = sorted_g.tail(20)[['broker_id', 'broker_name', 'buy', 'sell', 'net']].to_dict('records')
        sell_list.reverse() # 讓賣超最嚴重的排在前面
        # Summary
        total_buy = int(g['buy'].sum())
        total_sell = int(g['sell'].sum())
        total_net = int(g['net'].sum())
        return {
            'summary': {'total_buy': total_buy, 'total_sell': total_sell, 'net': total_net},
            'top_buy': buy_list,
            'top_sell': sell_list
        }
    
    result = {'date': target_date, 'stocks': {}}
    for stock_id, group in df.groupby('StockID'):
        result['stocks'][stock_id] = get_top_brokers(group)
    
    brokers_dir = config.DATA_DIR / "brokers"
    brokers_dir.mkdir(parents=True, exist_ok=True)
    json_out_file = brokers_dir / f"{target_date}.json"
    with open(json_out_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, separators=(',', ':'))
    log.info(f"✅ JSON 輸出完成，大小: {os.path.getsize(json_out_file)/1024:.1f} KB")

    # 更新 index.json
    index_file = config.DATA_DIR / "index.json"
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
    else:
        index_data = {"holders": [], "brokers": []}
    
    if target_date not in index_data.get("brokers", []):
        brokers_list = index_data.get("brokers", [])
        brokers_list.append(target_date)
        brokers_list.sort(reverse=True)
        index_data["brokers"] = brokers_list
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
        log.info(f"✅ 已更新 index.json 中的 brokers 日期")

    # 清除暫存檔
    log.info("開始清除暫存檔...")
    for f in parquet_files:
        try:
            f.unlink()
        except Exception as e:
            log.warning(f"無法刪除 {f.name}: {e}")

if __name__ == "__main__":
    main()
