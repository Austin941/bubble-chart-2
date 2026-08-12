import json
import re
import time
import os
import gzip
import pandas as pd
import requests
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
    
    # 抓取三大法人資料並整合
    t86_data = fetch_t86_data(date_str)
    
    # 計算大盤 (0000) 總和
    market_f_buy = market_f_sell = 0
    market_t_buy = market_t_sell = 0
    market_d_buy = market_d_sell = 0
    
    for sid, brokers in t86_data.items():
        if sid in all_stocks_data:
            stock_data = all_stocks_data[sid]
            
            # 將法人資料塞入 top_buy / top_sell
            for pseudo_broker in brokers:
                if pseudo_broker['net'] > 0:
                    stock_data['top_buy'].append(pseudo_broker)
                elif pseudo_broker['net'] < 0:
                    stock_data['top_sell'].append(pseudo_broker)
                
                # 累加至大盤
                if pseudo_broker['broker_name'] == '法人-外資':
                    market_f_buy += pseudo_broker['buy']
                    market_f_sell += pseudo_broker['sell']
                elif pseudo_broker['broker_name'] == '法人-投信':
                    market_t_buy += pseudo_broker['buy']
                    market_t_sell += pseudo_broker['sell']
                elif pseudo_broker['broker_name'] == '法人-自營商':
                    market_d_buy += pseudo_broker['buy']
                    market_d_sell += pseudo_broker['sell']
            
            # 重新排序
            stock_data['top_buy'] = sorted(stock_data['top_buy'], key=lambda x: x['net'], reverse=True)
            stock_data['top_sell'] = sorted(stock_data['top_sell'], key=lambda x: x['net'])
            
    # 新增虛擬股票 0000 (大盤彙總)
    all_stocks_data['0000'] = {
        'summary': {'total_buy': 0, 'total_sell': 0, 'net': 0},
        'top_buy': [],
        'top_sell': []
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

    if success_count > 0 or len(t86_data) > 0:
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
