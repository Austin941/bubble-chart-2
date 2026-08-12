import json
import time
import gzip
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
import pandas as pd

import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_split(sid, retries=2):
    """
    Fetch stock splits and capital reductions for a given stock ID using yfinance.
    We try both .TW (TWSE) and .TWO (TPEx) suffixes if we don't know the exchange, 
    but for Taiwan stocks, yf usually needs the correct suffix.
    """
    suffixes = ['.TW', '.TWO']
    
    for suffix in suffixes:
        ticker = f"{sid}{suffix}"
        for attempt in range(retries):
            try:
                t = yf.Ticker(ticker)
                # This might trigger a network request
                splits = t.splits
                
                # If we get data, or an empty Series (meaning no splits but valid ticker), return it
                if splits is not None:
                    # Convert to our dictionary format: { "YYYYMMDD": float }
                    res = {}
                    if not splits.empty:
                        for date_idx, ratio in splits.items():
                            date_str = date_idx.strftime('%Y%m%d')
                            res[date_str] = float(ratio)
                    return res
            except Exception as e:
                # If it's a 404, it might mean wrong suffix (e.g., .TW instead of .TWO)
                time.sleep(0.5)
                pass
    
    # If all attempts fail, return empty dict
    return {}

def main():
    logger.info("Starting fetch_capital_events.py")
    
    meta_file = Path(config.META_DIR) / "stocks.json"
    if not meta_file.exists():
        logger.error(f"{meta_file} not found! Run fetch_yahoo_brokers.py first.")
        return
        
    with open(meta_file, 'r', encoding='utf-8') as f:
        meta_data = json.load(f)
        
    stock_ids = list(meta_data.get('stocks', {}).keys())
    
    # We don't need to fetch market index (0000)
    if '0000' in stock_ids:
        stock_ids.remove('0000')
        
    logger.info(f"Fetching split history for {len(stock_ids)} stocks...")
    
    capital_events = {}
    
    # We load the existing capital_events.json to avoid fully wiping it out
    # if yfinance temporarily fails for some stocks.
    events_file = Path(config.DATA_DIR) / "capital_events.json"
    if events_file.exists():
        try:
            with open(events_file, 'r', encoding='utf-8') as f:
                capital_events = json.load(f)
        except Exception as e:
            logger.warning(f"Could not read {events_file}, starting fresh: {e}")
            
    success_count = 0
    updated_count = 0
    
    # 20 workers is safe for yfinance
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {executor.submit(fetch_split, sid): sid for sid in stock_ids}
        
        for future in as_completed(future_to_id):
            sid = future_to_id[future]
            try:
                splits = future.result()
                if splits:
                    # Append or update
                    if sid not in capital_events:
                        capital_events[sid] = splits
                        updated_count += 1
                    else:
                        # Check if there are new dates
                        old_len = len(capital_events[sid])
                        capital_events[sid].update(splits)
                        if len(capital_events[sid]) > old_len:
                            updated_count += 1
                            
                success_count += 1
                if success_count % 100 == 0:
                    logger.info(f"Progress: {success_count} / {len(stock_ids)} stocks processed.")
            except Exception as e:
                logger.error(f"Error processing {sid}: {e}")
                
    logger.info(f"Successfully checked {success_count} stocks. {updated_count} stocks had split updates.")
    
    # Save the data
    Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)
    with open(events_file, 'w', encoding='utf-8') as f:
        json.dump(capital_events, f, ensure_ascii=False, indent=2, sort_keys=True)
        
    logger.info(f"Saved split history to {events_file}")

if __name__ == "__main__":
    main()
