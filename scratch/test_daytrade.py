import requests

def fetch_twse_daytrade(date_str="20240812"):
    url = f"https://www.twse.com.tw/exchangeReport/TWTB4U?response=json&date={date_str}"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    tables = res.json().get('tables', [])
    for t in tables:
        print("TWSE table title:", t.get('title'))
        if 'data' in t:
            print("TWSE first row:", t['data'][0])

def fetch_tpex_daytrade(date_str="20240812"):
    roc_year = int(date_str[:4]) - 1911
    roc_date = f"{roc_year}/{date_str[4:6]}/{date_str[6:]}"
    url = f"https://www.tpex.org.tw/web/stock/trading/intraday_stat/intraday_trading_stat_result.php?l=zh-tw&d={roc_date}"
    res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    tables = res.json().get('tables', [])
    for t in tables:
        print("TPEx table title:", t.get('title'))
        if 'data' in t:
            print("TPEx first row:", t['data'][0])

fetch_twse_daytrade()
fetch_tpex_daytrade()
