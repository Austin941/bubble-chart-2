import os, time, sys, requests, datetime
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

HISTORY_PARQUET = Path('data/brokers_history.parquet')

# Get last 5 trading days dates
dates = []
d = datetime.date.today()
while len(dates) < 5:
    if d.weekday() < 5: # Monday to Friday
        dates.append(d.strftime('%Y%m%d'))
    d -= datetime.timedelta(days=1)

headers = {'User-Agent': 'Mozilla/5.0'}
all_records = []

for date_str in dates:
    print(f"Fetching TWSE Margin for {date_str}...")
    try:
        twse_margin_url = f'https://www.twse.com.tw/exchangeReport/MI_MARGN?response=json&date={date_str}&selectType=ALL'
        res = requests.get(twse_margin_url, headers=headers, timeout=15)
        data = res.json()
        for t in data.get('tables', []):
            if len(t.get('data', [])) > 100:
                for row in t['data']:
                    sid = row[0].strip()
                    if not ((len(sid) == 4 and sid.isdigit()) or (len(sid) == 6 and sid.startswith('00'))):
                        continue
                    
                    def parse_int(val):
                        try: return int(val.replace(',', ''))
                        except: return 0
                    
                    margin_buy = parse_int(row[2]) * 1000
                    margin_sell = parse_int(row[3]) * 1000
                    short_buy = parse_int(row[8]) * 1000
                    short_sell = parse_int(row[9]) * 1000
                    
                    all_records.extend([
                        {'date': date_str, 'stock_id': sid, 'broker_name': '信用-融資', 'buy': margin_buy, 'sell': margin_sell, 'net': margin_buy - margin_sell},
                        {'date': date_str, 'stock_id': sid, 'broker_name': '信用-融券', 'buy': short_buy, 'sell': short_sell, 'net': short_buy - short_sell}
                    ])
                break
    except Exception as e:
        print(f"Error for {date_str}: {e}")
    time.sleep(2)

if all_records:
    df = pd.DataFrame(all_records)
    print("New margin records:", len(df))
    if HISTORY_PARQUET.exists():
        existing_df = pd.read_parquet(HISTORY_PARQUET)
        combined = pd.concat([existing_df, df], ignore_index=True)
        combined.drop_duplicates(subset=['date', 'stock_id', 'broker_name'], keep='last', inplace=True)
        combined.to_parquet(HISTORY_PARQUET, index=False)
        print("Updated parquet size:", len(combined))
    else:
        df.to_parquet(HISTORY_PARQUET, index=False)
else:
    print("No records fetched")
