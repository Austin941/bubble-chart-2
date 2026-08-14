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
        dates.append((d.strftime('%Y%m%d'), f"{d.year-1911}/{d.strftime('%m/%d')}"))
    d -= datetime.timedelta(days=1)

headers = {'User-Agent': 'Mozilla/5.0'}
all_records = []

for date_str, tpex_date in dates:
    print(f"Fetching TPEx Margin for {tpex_date}...")
    try:
        tpex_margin_url = f'https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=json&d={tpex_date}'
        res = requests.get(tpex_margin_url, headers=headers, timeout=15, verify=False)
        data = res.json()
        
        # In TPEx, data might be in data['aaData'] or data['tables'][0]['data'] depending on API
        table_data = []
        if 'tables' in data and len(data['tables']) > 0:
            table_data = data['tables'][0].get('data', [])
        elif 'aaData' in data:
            table_data = data['aaData']
            
        if len(table_data) > 100:
            for row in table_data:
                sid = row[0].strip()
                if not ((len(sid) == 4 and sid.isdigit()) or (len(sid) == 6 and sid.startswith('00'))):
                    continue
                
                def parse_int(val):
                    try: return int(val.replace(',', ''))
                    except: return 0
                
                margin_buy = parse_int(row[3]) * 1000
                margin_sell = parse_int(row[4]) * 1000
                short_buy = parse_int(row[11]) * 1000
                short_sell = parse_int(row[12]) * 1000
                
                all_records.extend([
                    {'date': date_str, 'stock_id': sid, 'broker_name': '信用-融資', 'buy': margin_buy, 'sell': margin_sell, 'net': margin_buy - margin_sell},
                    {'date': date_str, 'stock_id': sid, 'broker_name': '信用-融券', 'buy': short_buy, 'sell': short_sell, 'net': short_buy - short_sell}
                ])
    except Exception as e:
        print(f"Error for {tpex_date}: {e}")
    time.sleep(2)

if all_records:
    df = pd.DataFrame(all_records)
    print("New TPEx margin records:", len(df))
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
