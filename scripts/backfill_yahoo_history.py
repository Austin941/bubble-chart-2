"""
泡泡圖 2.0 — Yahoo 歷史資料大回補腳本
這個腳本會讀取 parquet 內的所有股票，爬取 Yahoo Finance 網頁 DOM 獲取：
1. 大戶籌碼歷史 (儲存為 data/holders/YYYYMMDD.json)
2. 資券變化歷史 (回補至 brokers_history.parquet)

支援防中斷機制 (每 100 檔提交 Git Commit)。
"""
import sys, os, time, random, traceback, subprocess
import requests
from bs4 import BeautifulSoup
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from config import HOLDERS_DIR, BROKERS_DIR
from utils import save_json, load_json, get_request_headers, log

HISTORY_PARQUET = BROKERS_DIR.parent / 'brokers_history.parquet'
PROGRESS_FILE = BROKERS_DIR.parent / 'backfill_progress.json'

def get_all_sids():
    if not HISTORY_PARQUET.exists():
        return []
    table = pq.read_table(HISTORY_PARQUET)
    sids = list(set(table['stock_id'].to_pylist()))
    # Filter for standard equities (4 digits or ETF 6 chars starting with 00)
    return sorted([str(s) for s in sids if (len(str(s)) == 4 and str(s).isdigit()) or (len(str(s)) == 6 and str(s).startswith('00'))])

def scrape_yahoo_margin(sid):
    url = f'https://tw.stock.yahoo.com/quote/{sid}/margin'
    try:
        res = requests.get(url, headers=get_request_headers(), timeout=10)
        if res.status_code != 200:
            if res.status_code == 999:
                return '999'
            return []
        
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('div', class_='table-row')
        results = []
        for r in rows:
            cols = [div.text.strip() for div in r.find_all('div') if div.text.strip()]
            if len(cols) >= 10 and cols[0].startswith('202'):
                date_str = cols[0].replace('/', '') # '2026/08/12' -> '20260812'
                def parse_int(val):
                    try: return int(val.replace(',', ''))
                    except: return 0
                
                margin_buy = parse_int(cols[6]) * 1000
                margin_sell = parse_int(cols[7]) * 1000
                short_buy = parse_int(cols[8]) * 1000
                short_sell = parse_int(cols[9]) * 1000
                
                if margin_buy > 0 or margin_sell > 0 or short_buy > 0 or short_sell > 0:
                    results.append({
                        'date': date_str,
                        'stock_id': sid,
                        'broker_name': '信用-融資',
                        'buy': margin_buy,
                        'sell': margin_sell,
                        'net': margin_buy - margin_sell
                    })
                    results.append({
                        'date': date_str,
                        'stock_id': sid,
                        'broker_name': '信用-融券',
                        'buy': short_buy,
                        'sell': short_sell,
                        'net': short_buy - short_sell
                    })
        return results
    except Exception as e:
        log.warning(f"{sid} Margin Error: {e}")
        return []

def scrape_yahoo_holders(sid):
    url = f'https://tw.stock.yahoo.com/quote/{sid}/major-holders'
    try:
        res = requests.get(url, headers=get_request_headers(), timeout=10)
        if res.status_code != 200:
            if res.status_code == 999:
                return '999'
            return []
            
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.find_all('div', class_='table-row')
        results = []
        for r in rows:
            cols = [div.text.strip() for div in r.find_all('div') if div.text.strip()]
            # Columns: [0:Date, 1:散戶持股%, 2:大戶持股%, 3:董監持股%, 4:總股東人數]
            if len(cols) >= 5 and cols[0].startswith('202'):
                date_str = cols[0].replace('/', '')
                def parse_pct(val):
                    try: return float(val.replace('%', ''))
                    except: return 0.0
                
                # New Yahoo DOM: cols[3]=外資, cols[4]=大戶, cols[5]=董監
                whale_pct = parse_pct(cols[4]) if len(cols) > 4 else 0.0
                retail_pct = round(100.0 - whale_pct, 2)
                
                if retail_pct > 0 or whale_pct > 0:
                    results.append({
                        'date': date_str,
                        'stock_id': sid,
                        'whale_pct': whale_pct,
                        'retail_pct': retail_pct,
                        'big_vs_retail': round(whale_pct - retail_pct, 4)
                    })
        return results
    except Exception as e:
        log.warning(f"{sid} Holders Error: {e}")
        return []

def git_commit_progress():
    try:
        subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=False)
        subprocess.run(['git', 'config', 'user.email', 'github-actions[bot]@users.noreply.github.com'], check=False)
        subprocess.run(['git', 'add', 'data/'], check=False)
        subprocess.run(['git', 'commit', '-m', 'Auto backfill Yahoo historical data (partial)'], check=False)
        subprocess.run(['git', 'push'], check=False)
        log.info("✔ 已自動 Commit & Push 當前進度到 GitHub")
    except Exception as e:
        log.warning(f"Git Push 失敗: {e}")

def load_progress():
    if PROGRESS_FILE.exists():
        return load_json(PROGRESS_FILE)
    return {"completed": []}

def save_progress(prog):
    save_json(PROGRESS_FILE, prog)

def main():
    sids = get_all_sids()
    prog = load_progress()
    completed = set(prog.get("completed", []))
    
    holders_by_date = {}
    
    if HISTORY_PARQUET.exists():
        existing_df = pd.read_parquet(HISTORY_PARQUET)
    else:
        existing_df = pd.DataFrame(columns=['date', 'stock_id', 'broker_name', 'buy', 'sell', 'net'])
        
    new_margin_records = []
    
    count = 0
    total = len(sids)
    
    for i, sid in enumerate(sids):
        if sid in completed:
            continue
            
        log.info(f"[{i+1}/{total}] 處理 {sid}...")
        
        # 1. Margin
        margin_data = scrape_yahoo_margin(sid)
        if margin_data == '999':
            log.error("💥 遭遇 Yahoo 999 封鎖！中止程式並保存進度。")
            break
        elif isinstance(margin_data, list):
            new_margin_records.extend(margin_data)
            
        time.sleep(random.uniform(1.5, 3.0))
        
        # 2. Holders
        holders_data = scrape_yahoo_holders(sid)
        if holders_data == '999':
            log.error("💥 遭遇 Yahoo 999 封鎖！中止程式並保存進度。")
            break
        elif isinstance(holders_data, list):
            for h in holders_data:
                d = h['date']
                if d not in holders_by_date:
                    json_path = HOLDERS_DIR / f"{d}.json"
                    if json_path.exists():
                        holders_by_date[d] = load_json(json_path).get("stocks", {})
                    else:
                        holders_by_date[d] = {}
                
                holders_by_date[d][sid] = {
                    "whale_pct": h["whale_pct"],
                    "retail_pct": h["retail_pct"],
                    "big_vs_retail": h["big_vs_retail"]
                }
        
        completed.add(sid)
        prog["completed"] = list(completed)
        save_progress(prog)
        count += 1
        
        time.sleep(random.uniform(1.5, 3.0))
        
        # Batch save & commit every 100 stocks
        if count % 100 == 0:
            for d, stocks in holders_by_date.items():
                json_path = HOLDERS_DIR / f"{d}.json"
                save_json(json_path, {"date": d, "source": "YahooBackfill", "stocks": stocks})
            
            if new_margin_records:
                new_df = pd.DataFrame(new_margin_records)
                merged_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['date', 'stock_id', 'broker_name'], keep='last')
                merged_df = merged_df.sort_values(['date', 'stock_id'], ascending=[False, True])
                table = pa.Table.from_pandas(merged_df, preserve_index=False)
                pq.write_table(table, HISTORY_PARQUET, compression='snappy')
                existing_df = merged_df
                new_margin_records = []
            
            git_commit_progress()

    # Final Save
    if count > 0:
        for d, stocks in holders_by_date.items():
            json_path = HOLDERS_DIR / f"{d}.json"
            save_json(json_path, {"date": d, "source": "YahooBackfill", "stocks": stocks})
        
        if new_margin_records:
            new_df = pd.DataFrame(new_margin_records)
            merged_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['date', 'stock_id', 'broker_name'], keep='last')
            merged_df = merged_df.sort_values(['date', 'stock_id'], ascending=[False, True])
            table = pa.Table.from_pandas(merged_df, preserve_index=False)
            pq.write_table(table, HISTORY_PARQUET, compression='snappy')
            
        git_commit_progress()
        
    log.info(f"🎉 任務結束，本次共處理 {count} 檔股票。")

if __name__ == '__main__':
    main()
