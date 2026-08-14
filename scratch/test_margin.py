import requests
from bs4 import BeautifulSoup
url = 'https://tw.stock.yahoo.com/quote/2330/margin'
res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
soup = BeautifulSoup(res.text, 'html.parser')
rows = soup.find_all('div', class_='table-row')
for r in rows:
    cols = [div.text.strip() for div in r.find_all('div') if div.text.strip()]
    if len(cols) >= 10:
        print("Date col:", cols[0])
        break
