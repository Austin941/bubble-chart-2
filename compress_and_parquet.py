import os
import json
import gzip
import pandas as pd
from pathlib import Path

data_dir = Path("data/brokers")
history_file = Path("data/brokers_history.parquet")

records = []

# Process all existing GZ files to build parquet
for gz_file in data_dir.glob("*.json.gz"):
    date_str = gz_file.stem.split('.')[0] # e.g. 20260804
    print(f"Processing {gz_file.name}...")
    
    with gzip.open(gz_file, 'rt', encoding='utf-8') as gf:
        data = json.load(gf)
        
    # Extract records for parquet
    for stock_id, stock_data in data.get('stocks', {}).items():
        # process top_buy
        for broker in stock_data.get('top_buy', []):
            records.append({
                'date': date_str,
                'stock_id': stock_id,
                'broker_name': broker.get('broker_name', ''),
                'buy': broker.get('buy', 0),
                'sell': broker.get('sell', 0),
                'net': broker.get('net', 0)
            })
        # process top_sell
        for broker in stock_data.get('top_sell', []):
            records.append({
                'date': date_str,
                'stock_id': stock_id,
                'broker_name': broker.get('broker_name', ''),
                'buy': broker.get('buy', 0),
                'sell': broker.get('sell', 0),
                'net': broker.get('net', 0)
            })
            
if records:
    df = pd.DataFrame(records)
    
    # Sort and save
    df = df.sort_values(['date', 'stock_id', 'net'], ascending=[False, True, False])
    df.to_parquet(history_file, index=False)
    print(f"Saved {len(df)} total records to {history_file.name}")
else:
    print("No records found.")
