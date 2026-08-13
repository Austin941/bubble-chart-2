"""
將每個禮拜的資料 (20250822.json, 20250829.json...)
反向轉換為單檔股票的歷史序列 (history/2330.json)
讓前端畫線圖時，只需要發送一次 1KB 的請求，不需下載全市場資料。
"""
import sys, os
import glob
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from config import HOLDERS_DIR
from utils import save_json, load_json, log

HISTORY_DIR = HOLDERS_DIR / "history"

def main():
    log.info("開始建置單檔股票大戶歷史 JSON...")
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    
    # 找尋所有的 YYYYMMDD.json
    json_files = glob.glob(str(HOLDERS_DIR / "2*.json"))
    json_files = sorted([f for f in json_files if Path(f).name != "latest_holders.json"])
    
    # 資料結構: stock_id -> list of { date, whale_pct, retail_pct }
    history_map = defaultdict(list)
    
    for f in json_files:
        data = load_json(Path(f))
        date_str = data.get("date")
        if not date_str:
            continue
            
        stocks = data.get("stocks", {})
        for sid, info in stocks.items():
            # 取出需要畫圖的欄位
            record = {
                "date": date_str,
                "whale": info.get("whale_pct", 0),
                "retail": info.get("retail_pct", 0)
            }
            history_map[sid].append(record)
            
    # 寫出為單檔 json
    count = 0
    for sid, records in history_map.items():
        # 依照日期排序以防萬一
        records.sort(key=lambda x: x["date"])
        
        out_path = HISTORY_DIR / f"{sid}.json"
        save_json(out_path, records)
        count += 1
        
    log.info(f"成功建置 {count} 檔股票的歷史 JSON 於 {HISTORY_DIR}")

if __name__ == "__main__":
    main()
