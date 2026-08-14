import sys
import json
import time
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.append(str(Path('.').absolute()))
sys.path.append(str(Path('scripts').absolute()))
import config

def build_all_stock_packages():
    t0 = time.time()
    print("Starting build of unified stock packages (data/stocks/{symbol}.json)...")
    # 1. Load Meta
    meta_file = Path(config.DATA_DIR) / 'meta' / 'stocks.json'
    meta_stocks = {}
    if meta_file.exists():
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta_data = json.load(f)
            meta_stocks = meta_data.get('stocks', {})

    # 2. Load Parquet History
    history_file = Path(config.DATA_DIR) / 'brokers_history.parquet'
    if not history_file.exists():
        print("brokers_history.parquet not found!")
        return

    full_df = pd.read_parquet(history_file)
    print(f"Loaded {len(full_df)} records from Parquet")

    # Format dates as YYYY-MM-DD
    all_dates = sorted(full_df['date'].unique())
    last_20_dates = set(all_dates[-20:]) if len(all_dates) >= 20 else set(all_dates)
    last_60_dates = set(all_dates[-60:]) if len(all_dates) >= 60 else set(all_dates)
    today_str = datetime.now().strftime('%Y-%m-%d')

    # 3. Prepare output directory
    out_dir = Path(config.DATA_DIR) / 'stocks'
    out_dir.mkdir(parents=True, exist_ok=True)

    # 4. Group data per stock
    grouped = full_df.groupby('stock_id')
    total_stocks = len(grouped)
    print(f"Processing {total_stocks} stocks...")

    count = 0
    for sid, stock_df in grouped:
        stock_name = meta_stocks.get(sid, {}).get('name', sid)
        
        # --- A. Chip History (三大法人: 外資, 投信, 自營商) ---
        chip_records = []
        inst_df = stock_df[stock_df['broker_name'].str.startswith('法人-')]
        
        # Group by date for institutional
        for d, d_group in inst_df.groupby('date'):
            d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            f_net = int(d_group[d_group['broker_name'] == '法人-外資']['net'].sum() // 1000)
            t_net = int(d_group[d_group['broker_name'] == '法人-投信']['net'].sum() // 1000)
            d_net = int(d_group[d_group['broker_name'] == '法人-自營商']['net'].sum() // 1000)
            tot_net = f_net + t_net + d_net
            chip_records.append({
                "date": d_fmt,
                "foreign": f_net,
                "trust": t_net,
                "dealer": d_net,
                "total": tot_net
            })
        chip_records.sort(key=lambda x: x['date'])

        # --- B. Margin History (信用交易: 融資, 融券) ---
        margin_records = []
        margin_df = stock_df[stock_df['broker_name'].str.startswith('信用-')]
        
        for d, d_group in margin_df.groupby('date'):
            d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            m_net = int(d_group[d_group['broker_name'] == '信用-融資']['net'].sum() // 1000)
            s_net = int(d_group[d_group['broker_name'] == '信用-融券']['net'].sum() // 1000)
            # In our parquet, buy/sell represents volume in shares
            m_buy = int(d_group[d_group['broker_name'] == '信用-融資']['buy'].sum() // 1000)
            s_buy = int(d_group[d_group['broker_name'] == '信用-融券']['buy'].sum() // 1000)
            
            margin_records.append({
                "date": d_fmt,
                "marginBalance": m_buy, # Or cumulative
                "marginChange": m_net,
                "shortBalance": s_buy,
                "shortChange": s_net,
                "shortMarginRatio": round((s_buy / m_buy * 100) if m_buy > 0 else 0.0, 2)
            })
        margin_records.sort(key=lambda x: x['date'])

        # --- C. Daytrade History (當沖) ---
        daytrade_records = []
        daytrade_df = stock_df[stock_df['broker_name'] == '信用-當沖']
        for d, d_group in daytrade_df.groupby('date'):
            d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            vol = int(d_group['buy'].sum() // 1000)
            daytrade_records.append({
                "date": d_fmt,
                "volume": vol
            })
        daytrade_records.sort(key=lambda x: x['date'])

        # --- D. Holders History (集保大戶) ---
        holders_records = []
        holder_file = Path(config.DATA_DIR) / 'holders' / 'history' / f"{sid}.json"
        if holder_file.exists():
            try:
                with open(holder_file, 'r', encoding='utf-8') as hf:
                    h_list = json.load(hf)
                    for item in h_list:
                        d = item.get('date', '')
                        if len(d) == 8:
                            d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                            whale = float(item.get('whale_pct', item.get('whale', 0.0)))
                            holders_records.append({
                                "date": d_fmt,
                                "majorHoldersRatio": whale,
                                "foreignOwnershipRatio": 0.0 # Optional
                            })
                holders_records.sort(key=lambda x: x['date'])
            except Exception:
                pass

        # --- E. Top Brokers (券商分點: 近20日, 近60日) ---
        # Exclude institutions and margin rows
        reg_df = stock_df[~stock_df['broker_name'].str.startswith(('法人-', '信用-'))]

        def compute_top_brokers(subset_df):
            if subset_df.empty:
                return {"topBuyers": [], "topSellers": []}
            
            b_agg = subset_df.groupby('broker_name', as_index=False).agg({
                'buy': 'sum',
                'sell': 'sum',
                'net': 'sum'
            })
            b_agg['buy_lots'] = (b_agg['buy'] // 1000).astype(int)
            b_agg['sell_lots'] = (b_agg['sell'] // 1000).astype(int)
            b_agg['net_lots'] = (b_agg['net'] // 1000).astype(int)

            buyers = b_agg[b_agg['net_lots'] > 0].sort_values('net_lots', ascending=False).head(15)
            sellers = b_agg[b_agg['net_lots'] < 0].sort_values('net_lots', ascending=True).head(15)

            top_buyers = [
                {
                    "name": row['broker_name'],
                    "buy": int(row['buy_lots']),
                    "sell": int(row['sell_lots']),
                    "net": int(row['net_lots'])
                }
                for _, row in buyers.iterrows()
            ]
            top_sellers = [
                {
                    "name": row['broker_name'],
                    "buy": int(row['buy_lots']),
                    "sell": int(row['sell_lots']),
                    "net": int(row['net_lots'])
                }
                for _, row in sellers.iterrows()
            ]
            return {"topBuyers": top_buyers, "topSellers": top_sellers}

        df_20 = reg_df[reg_df['date'].isin(last_20_dates)]
        df_60 = reg_df[reg_df['date'].isin(last_60_dates)]

        top_brokers = {
            "days20": compute_top_brokers(df_20),
            "days60": compute_top_brokers(df_60)
        }

        # --- F. Combine Package ---
        package = {
            "symbol": sid,
            "name": stock_name,
            "updatedAt": today_str,
            "chipHistory": chip_records,
            "marginHistory": margin_records,
            "daytradeHistory": daytrade_records,
            "holdersHistory": holders_records,
            "topBrokers": top_brokers
        }

        out_path = out_dir / f"{sid}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(package, f, ensure_ascii=False, separators=(',', ':'))

        count += 1

    print(f"Successfully generated {count} unified stock JSONs in {time.time() - t0:.2f}s!")

if __name__ == '__main__':
    build_all_stock_packages()
