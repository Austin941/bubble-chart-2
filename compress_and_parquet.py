import os
import json
import gzip
import pandas as pd
from pathlib import Path

data_dir = Path("data/brokers")
history_file = Path("data/brokers_history.parquet")

records = []

# Convert existing JSONs to GZ and extract data for parquet
for json_file in data_dir.glob("*.json"):
    date_str = json_file.stem
    print(f"Processing {json_file.name}...")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Write to GZIP
    gz_file = data_dir / f"{date_str}.json.gz"
    with gzip.open(gz_file, 'wt', encoding='utf-8') as gf:
        json.dump(data, gf, ensure_ascii=False, separators=(',', ':'))
        
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
            
    # Remove original json to save space
    os.remove(json_file)
    print(f"Saved {gz_file.name} and removed original.")

if records:
    df = pd.DataFrame(records)
    
    # If history parquet exists, read and concat
    if history_file.exists():
        old_df = pd.read_parquet(history_file)
        df = pd.concat([old_df, df])
        
    # Drop duplicates just in case
    df = df.drop_duplicates(subset=['date', 'stock_id', 'broker_name'])
    
    # Sort and save
    df = df.sort_values(['date', 'stock_id', 'net'], ascending=[False, True, False])
    df.to_parquet(history_file, index=False)
    print(f"Saved {len(df)} total records to {history_file.name}")
else:
    print("No records found.")
