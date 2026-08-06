import json
import re
import time
import os
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.simplefilter('ignore')

import config

def get_today_str():
    return datetime.now().strftime('%Y%m%d')

def fetch_yahoo_stock(stock_id):
    # Yahoo TW handles raw IDs like '2330' and '8299' well without .TW or .TWO suffix in most cases.
    # If a suffix is required, we can try appending '.TWO' or '.TW' later.
    url = f"https://tw.stock.yahoo.com/quote/{stock_id}/broker-trading"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        # Mandatory sleep to prevent Yahoo WAF 999 IP ban
        time.sleep(1.5)
        
        for attempt in range(3):
            res = requests.get(url, headers=headers, timeout=10, verify=False)
            if res.status_code == 200:
                break
            if res.status_code == 999:
                time.sleep(2)
                continue
            return None
            
        if res.status_code != 200:
            return None
        
        # Extract buyer and seller lists from HTML
        buyer_match = re.search(r'"buyerRankList":(\[.*?\])', res.text)
        seller_match = re.search(r'"sellerRankList":(\[.*?\])', res.text)
        
        # Extract totals
        total_buy_match = re.search(r'"totalBuyVolK":"?([0-9.,]+)"?', res.text)
        total_sell_match = re.search(r'"totalSellVolK":"?([0-9.,]+)"?', res.text)
        
        if not buyer_match and not seller_match:
            return None
            
        buyers = json.loads(buyer_match.group(1)) if buyer_match else []
        sellers = json.loads(seller_match.group(1)) if seller_match else []
        
        def format_broker(b):
            # buyVolK is in lots (張). We multiply by 1000 for shares (股).
            buy_lots = float(str(b.get('buyVolK', 0)).replace(',', ''))
            sell_lots = float(str(b.get('sellVolK', 0)).replace(',', ''))
            buy = int(buy_lots * 1000)
            sell = int(sell_lots * 1000)
            net = buy - sell
            return {
                "broker_id": "",
                "broker_name": b.get('name', '未知'),
                "buy": buy,
                "sell": sell,
                "net": net
            }
            
        top_buy = [format_broker(b) for b in buyers]
        top_sell = [format_broker(b) for b in sellers]
        
        # Use exact totals if available, otherwise sum top 15
        total_buy = sum(b['buy'] for b in top_buy)
        total_sell = sum(b['sell'] for b in top_sell)
        
        if total_buy_match:
            total_buy = int(float(total_buy_match.group(1).replace(',', '')) * 1000)
        if total_sell_match:
            total_sell = int(float(total_sell_match.group(1).replace(',', '')) * 1000)
            
        return {
            "summary": {
                "total_buy": total_buy,
                "total_sell": total_sell,
                "net": total_buy - total_sell
            },
            "top_buy": top_buy,
            "top_sell": top_sell
        }
        
    except Exception as e:
        return None

def main():
    today = get_today_str()
    out_file = config.BROKERS_DIR / f"{today}.json"
    meta_file = config.META_DIR / "stocks.json"
    
    if not meta_file.exists():
        print("meta/stocks.json not found!")
        return
        
    with open(meta_file, 'r', encoding='utf-8') as f:
        meta_data = json.load(f)
        
    stock_ids = list(meta_data.get('stocks', {}).keys())
    
    results = {
        "date": today,
        "stocks": {}
    }
    
    print(f"Fetching data for {len(stock_ids)} stocks from Yahoo Finance...")
    
    success_count = 0
    with ThreadPoolExecutor(max_workers=1) as executor:
        future_to_id = {executor.submit(fetch_yahoo_stock, sid): sid for sid in stock_ids}
        
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            data = future.result()
            if data:
                results["stocks"][sid] = data
                success_count += 1
                if success_count % 100 == 0:
                    print(f"Progress: {success_count} stocks processed.")
                    
    print(f"Finished! Successfully fetched {success_count} / {len(stock_ids)} stocks.")
    
    if success_count > 0:
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, separators=(',', ':'), ensure_ascii=False)
            
        print(f"Saved to {out_file}")
        
        # Update index.json
        index_file = config.DATA_DIR / "index.json"
        if index_file.exists():
            with open(index_file, 'r', encoding='utf-8') as f:
                idx_data = json.load(f)
        else:
            idx_data = {"holders": [], "brokers": []}
            
        if today not in idx_data.get("brokers", []):
            if "brokers" not in idx_data:
                idx_data["brokers"] = []
            idx_data["brokers"].insert(0, today)
            # Keep latest 30 days
            idx_data["brokers"] = idx_data["brokers"][:30]
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(idx_data, f, indent=2)
                
        print("Update complete.")
    else:
        print("No data fetched. Aborting save.")

if __name__ == "__main__":
    main()
