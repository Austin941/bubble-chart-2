import requests
from bs4 import BeautifulSoup
import json
headers = {'User-Agent': 'Mozilla/5.0'}
res = requests.get('https://tw.stock.yahoo.com/quote/2330/major-holders', headers=headers)
soup = BeautifulSoup(res.text, 'html.parser')
headers = soup.find_all('div', class_='table-header')
with open('scratch/holders_headers.json', 'w', encoding='utf-8') as f:
    results = []
    for h in headers:
        cols = [d.text.strip() for d in h.find_all('div') if d.text.strip()]
        results.append(cols)
    
    rows = soup.find_all('li', class_='List(n)')
    results.append("ROWS:")
    for r in rows[:5]:
        cols = [d.text.strip() for d in r.find_all('div') if d.text.strip()]
        if cols and cols[0].startswith('202'):
            results.append(cols)
    json.dump(results, f, ensure_ascii=False, indent=2)
