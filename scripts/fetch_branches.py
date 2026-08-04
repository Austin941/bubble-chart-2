import os
import sys
import time
import argparse
import requests
import ddddocr
from PIL import Image
import io
from bs4 import BeautifulSoup
from pathlib import Path
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

# 忽略 Pandas 的警告
warnings.simplefilter(action='ignore', category=FutureWarning)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from utils import log, already_exists, today_str

# 建立 ddddocr 的全域實例 (Thread-safe in general, but we can instantiate per thread or once)
OCR_ENGINE = ddddocr.DdddOcr(show_ad=False)

def get_captcha_and_params(session: requests.Session):
    url = "https://bsr.twse.com.tw/bshtm/bsMenu.aspx"
    try:
        res = session.get(url, timeout=config.REQUEST_TIMEOUT)
        res.raise_for_status()
    except Exception as e:
        return None, None

    soup = BeautifulSoup(res.text, 'html.parser')
    params = {}
    for i in soup.find_all('input'):
        name = i.get('name')
        if name and name.startswith('__'):
            params[name] = i.get('value', '')
            
    captcha_img_url = None
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if 'CaptchaImage.aspx' in src:
            captcha_img_url = f"https://bsr.twse.com.tw/bshtm/{src}"
            break
            
    if not captcha_img_url:
        return None, None
        
    try:
        res_img = session.get(captcha_img_url, timeout=config.REQUEST_TIMEOUT)
        res_img.raise_for_status()
        img_bytes = res_img.content
    except Exception as e:
        return None, None
        
    return params, img_bytes

def solve_captcha(img_bytes: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(img_bytes))
    except Exception:
        return ""
    return OCR_ENGINE.classification(img_bytes)

def fetch_and_parse_csv(stock_id: str, max_retries: int = 15) -> pd.DataFrame:
    """抓取 CSV 並將雙欄排版打平正規化"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })

    csv_data = None
    for attempt in range(1, max_retries + 1):
        params, img_bytes = get_captcha_and_params(session)
        if not params or not img_bytes:
            time.sleep(1)
            continue
            
        captcha_text = solve_captcha(img_bytes)
        if len(captcha_text) != 5:
            continue

        payload = {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": params.get("__VIEWSTATE", ""),
            "__VIEWSTATEGENERATOR": params.get("__VIEWSTATEGENERATOR", ""),
            "__EVENTVALIDATION": params.get("__EVENTVALIDATION", ""),
            "RadioButton_Normal": "RadioButton_Normal",
            "TextBox_Stkno": stock_id,
            "CaptchaControl1": captcha_text,
            "btnOK": "查詢"
        }
        
        try:
            res_post = session.post("https://bsr.twse.com.tw/bshtm/bsMenu.aspx", data=payload, timeout=config.REQUEST_TIMEOUT)
            if "驗證碼錯誤" in res_post.text or ("驗證碼" in res_post.text and "錯誤" in res_post.text):
                continue
            if "查無資料" in res_post.text or "不存在" in res_post.text:
                log.info(f"[{stock_id}] 查無今日分點資料 (無交易或未開盤)")
                return pd.DataFrame()
                
            csv_url = "https://bsr.twse.com.tw/bshtm/bsContent.aspx"
            res_csv = session.get(csv_url, timeout=config.REQUEST_TIMEOUT)
            
            content_text = res_csv.text
            if "<html" in content_text.lower() or "<form" in content_text.lower() or "<!doctype" in content_text.lower():
                log.warning(f"[{stock_id}] 下載到 HTML 網頁而非 CSV，驗證可能失敗或被阻擋，重試")
                time.sleep(1)
                continue
                
            csv_data = res_csv.content
            break
        except Exception as e:
            time.sleep(1)
            continue

    if not csv_data:
        log.error(f"[{stock_id}] 超過最大重試次數，抓取失敗。")
        return pd.DataFrame()

    # 開始解析正規化 CSV
    try:
        # TWSE 分點資料通常是 Big5 編碼 (cp950) 且前兩行是標題與說明
        df_raw = pd.read_csv(io.BytesIO(csv_data), encoding="cp950", skiprows=2)
        
        # 雙欄切割: 左半邊
        left_cols = ["序號", "券商", "價格", "買進股數", "賣出股數"]
        # 右半邊通常是 "序號.1", "券商.1", ... 但有時欄位名稱可能有些微差異
        
        df_left = df_raw.iloc[:, 0:5].copy()
        df_left.columns = left_cols
        
        df_right = df_raw.iloc[:, 6:11].copy()
        df_right.columns = left_cols
        
        # 合併左右兩欄
        df_merged = pd.concat([df_left, df_right], ignore_index=True)
        # 移除空值 (有些券商欄位是 nan)
        df_merged = df_merged.dropna(subset=["券商"])
        
        # 解析券商名稱 (例如: "1021合庫台中" -> ID: "1021", Name: "合庫台中")
        # 若有全形空白或不規則字元，可使用 strip 整理
        def parse_broker(x):
            x = str(x).replace("　", "").strip()
            # 台灣券商代號固定為 4 碼 (可包含英文字母如 961F)
            if len(x) >= 4:
                return x[:4], x[4:].strip()
            return "", x

        parsed = df_merged["券商"].apply(parse_broker)
        df_merged["BrokerID"] = parsed.apply(lambda v: v[0])
        df_merged["BrokerName"] = parsed.apply(lambda v: v[1])
        df_merged["StockID"] = stock_id
        
        # 重新命名與挑選欄位
        df_merged.rename(columns={
            "價格": "Price",
            "買進股數": "BuyVolume",
            "賣出股數": "SellVolume"
        }, inplace=True)
        
        result_df = df_merged[["StockID", "BrokerID", "BrokerName", "Price", "BuyVolume", "SellVolume"]].copy()
        result_df["Price"] = pd.to_numeric(result_df["Price"], errors='coerce')
        result_df["BuyVolume"] = pd.to_numeric(result_df["BuyVolume"], errors='coerce').fillna(0).astype(int)
        result_df["SellVolume"] = pd.to_numeric(result_df["SellVolume"], errors='coerce').fillna(0).astype(int)
        
        log.info(f"[{stock_id}] 抓取並解析成功，共 {len(result_df)} 筆")
        return result_df
        
    except Exception as e:
        log.error(f"[{stock_id}] CSV 解析失敗: {e}")
        return pd.DataFrame()

def process_stock(stock_id: str) -> pd.DataFrame:
    return fetch_and_parse_csv(stock_id)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-idx", type=int, default=0, help="目前的批次索引 (0-based)")
    parser.add_argument("--total-chunks", type=int, default=1, help="總共切分為幾個批次")
    args = parser.parse_args()

    # 讀取全市場股票清單
    stocks_path = config.META_DIR / "stocks.json"
    if not stocks_path.exists():
        log.error(f"找不到股票清單: {stocks_path}")
        sys.exit(1)
        
    import json
    with open(stocks_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        stocks_dict = data.get("stocks", data)
    
    # 取得所有股票代號並過濾掉權證 (長度大於 4)
    all_stocks = [k for k in stocks_dict.keys() if len(str(k)) <= 4]
    all_stocks = sorted(all_stocks)
    
    import math
    chunk_size = math.ceil(len(all_stocks) / args.total_chunks)
    start_idx = args.chunk_idx * chunk_size
    end_idx = min(start_idx + chunk_size, len(all_stocks))
    
    target_stocks = all_stocks[start_idx:end_idx]
    log.info(f"Chunk {args.chunk_idx+1}/{args.total_chunks} - 預計處理 {len(target_stocks)} 檔股票 (從 {start_idx} 到 {end_idx-1})")

    today = today_str()
    out_file = config.BRANCHES_DIR / f"chunk_{args.chunk_idx}_{today}.parquet"
    
    if already_exists(out_file):
        log.info(f"此 Chunk 今日資料已存在 ({out_file})，跳過。")
        return

    all_data = []
    
    # 多執行緒平行抓取
    max_workers = 3
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_stock = {executor.submit(process_stock, sid): sid for sid in target_stocks}
        
        for future in as_completed(future_to_stock):
            sid = future_to_stock[future]
            try:
                df = future.result()
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                log.error(f"[{sid}] 發生未預期錯誤: {e}")
                
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        final_df.to_parquet(out_file, index=False, engine="pyarrow", compression="snappy")
        log.info(f"✅ Chunk {args.chunk_idx} 處理完成，已儲存至 {out_file} (總筆數: {len(final_df)})")
    else:
        log.warning(f"Chunk {args.chunk_idx} 沒有抓到任何資料，可能今日非交易日。")
        # 仍產出空的 Parquet 以便後續步驟不失敗
        pd.DataFrame(columns=["StockID", "BrokerID", "BrokerName", "Price", "BuyVolume", "SellVolume"]).to_parquet(out_file, index=False)

if __name__ == "__main__":
    main()
