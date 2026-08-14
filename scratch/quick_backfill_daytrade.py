import os, time, sys, requests, datetime
import pandas as pd
import pyarrow.parquet as pq
from pathlib import Path

HISTORY_PARQUET = Path('data/brokers_history.parquet')

dates = []
d = datetime.date.today()
while len(dates) < 5:
    if d.weekday() < 5: # Monday to Friday
        dates.append((d.strftime('%Y%m%d'), f"{d.year-1911}/{d.strftime('%m/%d')}"))
    d -= datetime.timedelta(days=1)

headers = {'User-Agent': 'Mozilla/5.0'}
all_records = []

for date_str, tpex_date in dates:
    print(f"Fetching Daytrade for {date_str} / {tpex_date}...")
    
    # 1. TWSE Daytrade
    try:
        twse_url = f'https://www.twse.com.tw/exchangeReport/TWTB4U?response=json&date={date_str}'
        res = requests.get(twse_url, headers=headers, timeout=15)
        data = res.json()
        for t in data.get('tables', []):
            if len(t.get('data', [])) > 100:
                for row in t['data']:
                    sid = row[0].strip()
                    if not ((len(sid) == 4 and sid.isdigit()) or (len(sid) == 6 and sid.startswith('00'))): continue
                    def parse_int(val):
                        try: return int(val.replace(',', ''))
                        except: return 0
                    
                    vol = parse_int(row[3])
                    if vol > 0:
                        all_records.append({'date': date_str, 'stock_id': sid, 'broker_name': '信用-當沖', 'buy': vol, 'sell': vol, 'net': 0})
                break
    except Exception as e:
        print(f"TWSE error: {e}")
        
    # 2. TPEx Daytrade
    try:
        tpex_url = f'https://www.tpex.org.tw/web/stock/trading/intraday_stat/intraday_trading_stat.php?l=zh-tw&d={tpex_date}&s=0,asc,0&o=json'
        res = requests.get(tpex_url, headers=headers, timeout=15, verify=False)
        data = res.json()
        table_data = []
        if 'tables' in data and len(data['tables']) > 0:
            table_data = data['tables'][0].get('data', [])
        elif 'aaData' in data:
            table_data = data['aaData']
            
        if len(table_data) > 100:
            for row in table_data:
                sid = row[0].strip()
                if not ((len(sid) == 4 and sid.isdigit()) or (len(sid) == 6 and sid.startswith('00'))): continue
                def parse_int(val):
                    try: return int(val.replace(',', ''))
                    except: return 0
                
                vol = parse_int(row[3])
                if vol > 0:
                    all_records.append({'date': date_str, 'stock_id': sid, 'broker_name': '信用-當沖', 'buy': vol, 'sell': vol, 'net': 0})
    except Exception as e:
        print(f"TPEx error: {e}")
        
    time.sleep(2)

if all_records:
    df = pd.DataFrame(all_records)
    print("New daytrade records:", len(df))
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
