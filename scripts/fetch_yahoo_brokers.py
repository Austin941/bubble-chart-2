import json
import re
import time
import os
import gzip
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
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

def wait_until_target_time(target_hour=17, target_minute=0):
    """
    等待直到台灣時間的指定時間。
    """
    tw_tz = timezone(timedelta(hours=8))
    now = datetime.now(tw_tz)
    target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    
    if now >= target_time:
        print(f"Current time {now.strftime('%H:%M:%S')} is past {target_hour:02d}:{target_minute:02d}. Starting immediately.")
        return
        
    wait_seconds = (target_time - now).total_seconds()
    print(f"Idling for {int(wait_seconds)} seconds until {target_hour:02d}:{target_minute:02d}...")
    time.sleep(wait_seconds)
    print("Time reached! Starting scrape...")

def main():
    # 確保過了下午 5 點才開始抓
    wait_until_target_time(17, 0)
    
    date_str = get_today_str()
    meta_file = config.META_DIR / "stocks.json"
    
    if not meta_file.exists():
        print("meta/stocks.json not found!")
        return
        
    with open(meta_file, 'r', encoding='utf-8') as f:
        meta_data = json.load(f)
        
    stock_ids = list(meta_data.get('stocks', {}).keys())
    
    all_stocks_data = {}
    
    print(f"Fetching data for {len(stock_ids)} stocks from Yahoo Finance...")
    
    success_count = 0
    with ThreadPoolExecutor(max_workers=1) as executor:
        future_to_id = {executor.submit(fetch_yahoo_stock, sid): sid for sid in stock_ids}
        
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            stock_data = future.result()
            if stock_data:
                all_stocks_data[sid] = stock_data
                success_count += 1
                if success_count % 100 == 0:
                    print(f"Progress: {success_count} stocks processed.")
                    
    print(f"Successfully fetched data for {success_count} stocks.")
    
    if success_count > 0:
        # Save the data to JSON GZ
        out_dir = Path(config.DATA_DIR) / 'brokers'
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{date_str}.json.gz"
        
        output_data = {
            'date': date_str,
            'stocks': all_stocks_data
        }
        
        with gzip.open(out_file, 'wt', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, separators=(',', ':'))
            
        print(f"Data saved to {out_file} (compressed)")
        
        # Update index.json
        index_file = Path(config.DATA_DIR) / 'index.json'
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
        except FileNotFoundError:
            index_data = {}
            
        if 'brokers' not in index_data:
            index_data['brokers'] = []
        
        if date_str not in index_data['brokers']:
            index_data['brokers'].insert(0, date_str)
            
        index_data['last_updated'] = datetime.now().isoformat()
        
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, separators=(',', ':'))
            
        print(f"Updated {index_file}")

        # --- Append to Parquet History ---
        print("Updating Parquet history...")
        history_file = Path(config.DATA_DIR) / 'brokers_history.parquet'
        records = []
        for sid, stock_data in all_stocks_data.items():
            for broker in stock_data.get('top_buy', []):
                records.append({
                    'date': date_str,
                    'stock_id': sid,
                    'broker_name': broker.get('broker_name', ''),
                    'buy': broker.get('buy', 0),
                    'sell': broker.get('sell', 0),
                    'net': broker.get('net', 0)
                })
            for broker in stock_data.get('top_sell', []):
                records.append({
                    'date': date_str,
                    'stock_id': sid,
                    'broker_name': broker.get('broker_name', ''),
                    'buy': broker.get('buy', 0),
                    'sell': broker.get('sell', 0),
                    'net': broker.get('net', 0)
                })
                
        if records:
            df = pd.DataFrame(records)
            if history_file.exists():
                try:
                    old_df = pd.read_parquet(history_file)
                    # Remove today's data if it somehow exists to prevent duplicates
                    old_df = old_df[old_df['date'] != date_str]
                    df = pd.concat([old_df, df])
                except Exception as e:
                    print(f"Failed to read existing parquet: {e}")
                    
            # Drop strict duplicates just in case
            df = df.drop_duplicates(subset=['date', 'stock_id', 'broker_name'])
            # Sort values
            df = df.sort_values(['date', 'stock_id', 'net'], ascending=[False, True, False])
            
            df.to_parquet(history_file, index=False)
            print(f"Successfully appended {len(records)} records to {history_file.name}. Total history size: {len(df)}")
        else:
            print("No records to append to Parquet.")
    else:
        print("No data fetched. Aborting save.")

if __name__ == "__main__":
    main()
