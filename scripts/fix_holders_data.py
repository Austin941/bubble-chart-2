import sys, os, time, json
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import pandas as pd

sys.path.append(str(Path('.').absolute()))
sys.path.append(str(Path('scripts').absolute()))
import config

DATA_DIR = Path(config.DATA_DIR)
HOLDERS_HIST_DIR = DATA_DIR / 'holders' / 'history'
STOCKS_DIR = DATA_DIR / 'stocks'

HOLDERS_HIST_DIR.mkdir(parents=True, exist_ok=True)
STOCKS_DIR.mkdir(parents=True, exist_ok=True)

def fetch_correct_holders(sid):
    url = f'https://tw.stock.yahoo.com/quote/{sid}/major-holders'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('div', class_='table-row')
        
        history_list = []
        for r in rows:
            cols = [d.text.strip() for d in r.find_all('div') if d.text.strip()]
            if len(cols) >= 5 and cols[0].startswith('202'):
                date_raw = cols[0].replace('/', '') # YYYYMMDD
                def parse_val(v):
                    try:
                        return float(v.replace('%', '').replace(',', ''))
                    except:
                        return None
                
                foreign = parse_val(cols[2]) if len(cols) > 2 else None
                whale = parse_val(cols[3]) if len(cols) > 3 else None
                directors = parse_val(cols[4]) if len(cols) > 4 else None
                
                if foreign is not None or whale is not None:
                    history_list.append({
                        "date": date_raw,
                        "whale": whale if whale is not None else 0.0,
                        "foreign": foreign if foreign is not None else 0.0,
                        "directors": directors if directors is not None else 0.0,
                        "retail": round(100.0 - whale, 2) if (whale is not None and whale > 0) else 0.0
                    })
        history_list.sort(key=lambda x: x['date'])
        return history_list
    except Exception as e:
        print(f"Error fetching {sid}: {e}")
        return None

def update_stock_json(sid, holders_list):
    stock_json_path = STOCKS_DIR / f"{sid}.json"
    if not stock_json_path.exists():
        return
    try:
        with open(stock_json_path, 'r', encoding='utf-8') as f:
            stock_data = json.load(f)
        
        formatted_holders = []
        for h in holders_list:
            if h.get('whale', 0.0) > 0 or h.get('foreign', 0.0) > 0:
                d = h['date']
                d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d
                formatted_holders.append({
                    "date": d_fmt,
                    "majorHoldersRatio": h.get('whale', 0.0),
                    "foreignOwnershipRatio": h.get('foreign', 0.0)
                })
        formatted_holders.sort(key=lambda x: x['date'])
        stock_data['holdersHistory'] = formatted_holders
        
        with open(stock_json_path, 'w', encoding='utf-8') as f:
            json.dump(stock_data, f, ensure_ascii=False, separators=(',', ':'))
    except Exception as e:
        print(f"Error updating stock JSON {sid}: {e}")

def update_single_stock(sid):
    holders_list = fetch_correct_holders(sid)
    if holders_list:
        # 1. Save to holders/history/{sid}.json
        with open(HOLDERS_HIST_DIR / f"{sid}.json", 'w', encoding='utf-8') as f:
            json.dump(holders_list, f, ensure_ascii=False, separators=(',', ':'))
        # 2. Update data/stocks/{sid}.json
        update_stock_json(sid, holders_list)
        print(f"Updated {sid}: latest foreign={holders_list[-1].get('foreign')}%, whale={holders_list[-1].get('whale')}%")
        return True
    return False

if __name__ == '__main__':
    # Fix key stocks first
    key_stocks = ['6770', '2308', '2330', '2317', '2454', '2382', '3231', '2603', '2609', '2615']
    for sid in key_stocks:
        update_single_stock(sid)
        time.sleep(1.0)
