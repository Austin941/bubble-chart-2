import yfinance as yf
import pandas as pd
import time
import random
import logging
from datetime import datetime
import sys
import os

# 確保在 Windows 終端機印出 Emoji 不會報錯 (cp950 error)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 目標觀察商品與其 Yahoo Finance 代號
MARKET_ASSETS = {
    "大宗商品 (Commodities)": {
        "原油 (WTI近月)": "CL=F",
        "黃金 (近月)": "GC=F",
    },
    "指數與波動率 (Indices & VIX)": {
        "加權指數 (^TWII)": "^TWII",
        "恐慌指數 (VIX)": "^VIX",
    },
    "外匯市場 (Forex)": {
        "美元指數 (DXY)": "DX-Y.NYB",
        "美元/台幣": "TWD=X",
        "美元/日圓": "JPY=X",
        "歐元/美元": "EURUSD=X"
    }
}

def fetch_data_with_retry(ticker_symbol, max_retries=3):
    """
    實作防封鎖機制的抓取函數
    嚴格遵守單執行緒、隨機延遲與退避重試
    """
    for attempt in range(max_retries):
        try:
            # 隨機延遲 1.5 到 3 秒 (遵守防封鎖鐵律)
            sleep_time = random.uniform(1.5, 3.0)
            logging.info(f"等待 {sleep_time:.2f} 秒後抓取 {ticker_symbol}...")
            time.sleep(sleep_time)
            
            ticker = yf.Ticker(ticker_symbol)
            # 抓取最近 5 天的資料以確保能取到前一個交易日
            hist = ticker.history(period="5d")
            
            if hist.empty:
                logging.warning(f"[{ticker_symbol}] 取得空資料，可能遭遇限制或無資料。")
                # 可能是被暫時限制，拉長等待時間
                backoff = 10 * (attempt + 1)
                logging.info(f"退避休眠 {backoff} 秒...")
                time.sleep(backoff)
                continue
                
            return hist
            
        except Exception as e:
            logging.error(f"[{ticker_symbol}] 發生錯誤: {e}")
            backoff = 10 * (attempt + 1)
            logging.info(f"退避休眠 {backoff} 秒...")
            time.sleep(backoff)
            
    logging.error(f"[{ticker_symbol}] 達到最大重試次數，放棄抓取。")
    return None

def generate_report():
    report_lines = []
    report_lines.append(f"# 每日市場觀察報告")
    report_lines.append(f"**生成時間:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    for category, assets in MARKET_ASSETS.items():
        report_lines.append(f"## {category}")
        report_lines.append("| 商品 | 最新收盤價 | 前日收盤價 | 漲跌幅 | 狀態 |")
        report_lines.append("|---|---|---|---|---|")
        
        for name, symbol in assets.items():
            hist = fetch_data_with_retry(symbol)
            if hist is not None and len(hist) >= 2:
                # 取得最新與前一交易日的收盤價
                latest_close = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                
                change = latest_close - prev_close
                change_pct = (change / prev_close) * 100
                
                # 狀態標示 (箭頭與符號)
                status = "🟢 上漲" if change > 0 else ("🔴 下跌" if change < 0 else "⚪ 持平")
                if change_pct > 2:
                    status = "🔥 暴漲"
                elif change_pct < -2:
                    status = "🩸 暴跌"
                    
                report_lines.append(
                    f"| {name} ({symbol}) | {latest_close:.3f} | {prev_close:.3f} | {change_pct:+.2f}% | {status} |"
                )
            else:
                report_lines.append(f"| {name} ({symbol}) | 抓取失敗 | - | - | ⚠️ |")
                
        report_lines.append("\n")
        
    return "\n".join(report_lines)

if __name__ == "__main__":
    logging.info("開始執行每日市場觀察抓取作業...")
    report_md = generate_report()
    
    # 確保 data 目錄存在
    os.makedirs("data", exist_ok=True)
    report_path = os.path.join("data", "market_report.md")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
        
    logging.info(f"報告已成功生成並儲存至 {report_path}")
    print("\n" + "="*40 + "\n")
    print(report_md)
