import sys, os, time
from pathlib import Path
sys.path.insert(0, str(Path('scripts').absolute()))
from backfill_yahoo_history import scrape_yahoo_margin, HISTORY_PARQUET
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sids = ['2330', '2317', '2454', '2382']
new_records = []

for sid in sids:
    print(f"Scraping margin for {sid}...")
    margin = scrape_yahoo_margin(sid)
    if isinstance(margin, list):
        new_records.extend(margin)
    time.sleep(1)

if new_records:
    df = pd.DataFrame(new_records)
    print("New margin records:", len(df))
    if HISTORY_PARQUET.exists():
        existing_df = pd.read_parquet(HISTORY_PARQUET)
        combined = pd.concat([existing_df, df], ignore_index=True)
        combined.drop_duplicates(subset=['date', 'stock_id', 'broker_name'], keep='last', inplace=True)
        combined.to_parquet(HISTORY_PARQUET, index=False)
        print("Updated parquet size:", len(combined))
    else:
        df.to_parquet(HISTORY_PARQUET, index=False)
        print("Created new parquet")
else:
    print("No records fetched")
