import os
import glob
import json
import gzip
import requests
import time
from pathlib import Path

def fetch_t86_data(date_str):
    print(f'Fetching T86 data for {date_str}...')
    t86_stocks = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # 1. TWSE
    twse_url = f'https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALL'
    try:
        res = requests.get(twse_url, headers=headers, timeout=15)
        data = res.json()
        if 'data' in data and data['data']:
            fields = data['fields']
            sid_idx = fields.index('證券代號')
            buy_f_idx = next(i for i, f in enumerate(fields) if '外陸資買進股數' in f and '不含' in f)
            sell_f_idx = next(i for i, f in enumerate(fields) if '外陸資賣出股數' in f and '不含' in f)
            buy_fd_idx = next((i for i, f in enumerate(fields) if '外資自營商買進股數' in f), -1)
            sell_fd_idx = next((i for i, f in enumerate(fields) if '外資自營商賣出股數' in f), -1)
            buy_t_idx = next(i for i, f in enumerate(fields) if '投信買進股數' in f)
            sell_t_idx = next(i for i, f in enumerate(fields) if '投信賣出股數' in f)
            
            buy_ds_idx = next((i for i, f in enumerate(fields) if '自營商買進股數(自行買賣)' in f), -1)
            sell_ds_idx = next((i for i, f in enumerate(fields) if '自營商賣出股數(自行買賣)' in f), -1)
            buy_dh_idx = next((i for i, f in enumerate(fields) if '自營商買進股數(避險)' in f), -1)
            sell_dh_idx = next((i for i, f in enumerate(fields) if '自營商賣出股數(避險)' in f), -1)
            
            if buy_ds_idx == -1:
                buy_ds_idx = next(i for i, f in enumerate(fields) if '自營商買進股數' in f)
                sell_ds_idx = next(i for i, f in enumerate(fields) if '自營商賣出股數' in f)
                buy_dh_idx = -1
                sell_dh_idx = -1

            for row in data['data']:
                sid = row[sid_idx].strip()
                def parse_int(val):
                    try: return int(val.replace(',', ''))
                    except: return 0
                
                f_buy = parse_int(row[buy_f_idx]); f_sell = parse_int(row[sell_f_idx])
                fd_buy = parse_int(row[buy_fd_idx]) if buy_fd_idx != -1 else 0
                fd_sell = parse_int(row[sell_fd_idx]) if sell_fd_idx != -1 else 0
                t_buy = parse_int(row[buy_t_idx]); t_sell = parse_int(row[sell_t_idx])
                
                ds_buy = parse_int(row[buy_ds_idx]); ds_sell = parse_int(row[sell_ds_idx])
                dh_buy = parse_int(row[buy_dh_idx]) if buy_dh_idx != -1 else 0
                dh_sell = parse_int(row[sell_dh_idx]) if sell_dh_idx != -1 else 0
                
                d_buy = ds_buy + dh_buy
                d_sell = ds_sell + dh_sell
                
                t86_stocks[sid] = [
                    {'broker_name': '法人-外資', 'buy': f_buy, 'sell': f_sell, 'net': f_buy - f_sell}
                ]
                if fd_buy > 0 or fd_sell > 0:
                    t86_stocks[sid].append({'broker_name': '外資自營商', 'buy': fd_buy, 'sell': fd_sell, 'net': fd_buy - fd_sell})
                
                t86_stocks[sid].extend([
                    {'broker_name': '法人-投信', 'buy': t_buy, 'sell': t_sell, 'net': t_buy - t_sell},
                    {'broker_name': '法人-自營商', 'buy': d_buy, 'sell': d_sell, 'net': d_buy - d_sell}
                ])
    except Exception as e:
        print(f'TWSE error: {e}')

    # 2. TPEx
    twn_year = int(date_str[:4]) - 1911
    tpex_date = f'{twn_year}/{date_str[4:6]}/{date_str[6:]}'
    tpex_url = f'https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&o=json&se=EW&t=D&d={tpex_date}'
    try:
        res = requests.get(tpex_url, headers=headers, timeout=15)
        data = res.json()
        
        table_data = []
        if 'tables' in data and len(data['tables']) > 0:
            table_data = data['tables'][0].get('data', [])
        elif 'aaData' in data:
            table_data = data['aaData']
            
        if table_data:
            for row in table_data:
                sid = row[0].strip()
                def parse_int(val):
                    try: return int(val.replace(',', ''))
                    except: return 0
                
                f_buy = parse_int(row[2]); f_sell = parse_int(row[3])
                fd_buy = parse_int(row[5]); fd_sell = parse_int(row[6])
                t_buy = parse_int(row[11]); t_sell = parse_int(row[12])
                
                ds_buy = parse_int(row[14]); ds_sell = parse_int(row[15])
                dh_buy = parse_int(row[17]); dh_sell = parse_int(row[18])
                d_buy = ds_buy + dh_buy
                d_sell = ds_sell + dh_sell
                
                t86_stocks[sid] = [
                    {'broker_name': '法人-外資', 'buy': f_buy, 'sell': f_sell, 'net': f_buy - f_sell}
                ]
                if fd_buy > 0 or fd_sell > 0:
                    t86_stocks[sid].append({'broker_name': '外資自營商', 'buy': fd_buy, 'sell': fd_sell, 'net': fd_buy - fd_sell})
                
                t86_stocks[sid].extend([
                    {'broker_name': '法人-投信', 'buy': t_buy, 'sell': t_sell, 'net': t_buy - t_sell},
                    {'broker_name': '法人-自營商', 'buy': d_buy, 'sell': d_sell, 'net': d_buy - d_sell}
                ])
    except Exception as e:
        print(f'TPEx error: {e}')
        
    return t86_stocks

def main():
    brokers_dir = Path("data/brokers")
    files = glob.glob(str(brokers_dir / "*.json.gz"))
    
    for filepath in files:
        filename = os.path.basename(filepath)
        date_str = filename.split('.')[0]
        
        # Load existing JSON
        print(f"\nProcessing {filename}...")
        try:
            with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                daily_data = json.load(f)
        except Exception as e:
            print(f"Failed to read {filename}: {e}")
            continue
            
        all_stocks_data = daily_data.get('stocks', {})
        
        # Check if already patched
        
            
        t86_data = fetch_t86_data(date_str)
        if not t86_data:
            print(f"No T86 data found for {date_str}. Skipping.")
            continue
            
        # Merge logic
        market_f_buy = market_f_sell = 0
        market_t_buy = market_t_sell = 0
        market_d_buy = market_d_sell = 0
        
        for sid, brokers in t86_data.items():
            if sid not in all_stocks_data:
                # If the stock wasn't scraped by Yahoo for some reason, we can still add it!
                all_stocks_data[sid] = {'summary': {'total_buy':0, 'total_sell':0, 'net':0}, 'top_buy': [], 'top_sell': []}
                
            stock_data = all_stocks_data[sid]
            for pseudo_broker in brokers:
                if pseudo_broker['net'] > 0:
                    stock_data['top_buy'].append(pseudo_broker)
                elif pseudo_broker['net'] < 0:
                    stock_data['top_sell'].append(pseudo_broker)
                    
                if pseudo_broker['broker_name'] == '法人-外資':
                    market_f_buy += pseudo_broker['buy']
                    market_f_sell += pseudo_broker['sell']
                elif pseudo_broker['broker_name'] == '法人-投信':
                    market_t_buy += pseudo_broker['buy']
                    market_t_sell += pseudo_broker['sell']
                elif pseudo_broker['broker_name'] == '法人-自營商':
                    market_d_buy += pseudo_broker['buy']
                    market_d_sell += pseudo_broker['sell']
                    
            stock_data['top_buy'] = sorted(stock_data['top_buy'], key=lambda x: x['net'], reverse=True)
            stock_data['top_sell'] = sorted(stock_data['top_sell'], key=lambda x: x['net'])
            
        # Market total (0000)
        all_stocks_data['0000'] = {
            'summary': {'total_buy': 0, 'total_sell': 0, 'net': 0},
            'top_buy': [], 'top_sell': []
        }
        market_brokers = [
            {'broker_name': '法人-外資', 'buy': market_f_buy, 'sell': market_f_sell, 'net': market_f_buy - market_f_sell},
            {'broker_name': '法人-投信', 'buy': market_t_buy, 'sell': market_t_sell, 'net': market_t_buy - market_t_sell},
            {'broker_name': '法人-自營商', 'buy': market_d_buy, 'sell': market_d_sell, 'net': market_d_buy - market_d_sell}
        ]
        for b in market_brokers:
            if b['net'] > 0:
                all_stocks_data['0000']['top_buy'].append(b)
            elif b['net'] < 0:
                all_stocks_data['0000']['top_sell'].append(b)
        all_stocks_data['0000']['top_buy'] = sorted(all_stocks_data['0000']['top_buy'], key=lambda x: x['net'], reverse=True)
        all_stocks_data['0000']['top_sell'] = sorted(all_stocks_data['0000']['top_sell'], key=lambda x: x['net'])

        daily_data['stocks'] = all_stocks_data
        
        # Save back
        print(f"Writing patched {filename}...")
        json_bytes = json.dumps(daily_data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        with gzip.open(filepath, 'wb') as f:
            f.write(json_bytes)
            
        time.sleep(3) # Delay between days
        
    print("\nPatching complete!")

if __name__ == "__main__":
    main()
