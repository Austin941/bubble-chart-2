import json
import requests
import re
import urllib3
urllib3.disable_warnings()

headers = {'User-Agent': 'Mozilla/5.0'}
res = requests.get('https://tw.stock.yahoo.com/quote/8299/broker-trading', headers=headers, verify=False)
buyer_match = re.search(r'"buyerRankList":(\[.*?\])', res.text)
seller_match = re.search(r'"sellerRankList":(\[.*?\])', res.text)
total_buy_match = re.search(r'"totalBuyVolK":"?([0-9.,]+)"?', res.text)
total_sell_match = re.search(r'"totalSellVolK":"?([0-9.,]+)"?', res.text)

buyers = json.loads(buyer_match.group(1))
sellers = json.loads(seller_match.group(1))

def format_broker(b):
    buy = int(float(str(b.get('buyVolK', 0)).replace(',', '')) * 1000)
    sell = int(float(str(b.get('sellVolK', 0)).replace(',', '')) * 1000)
    return {'broker_id': '', 'broker_name': b.get('name', '未知'), 'buy': buy, 'sell': sell, 'net': buy - sell}

top_buy = [format_broker(b) for b in buyers]
top_sell = [format_broker(b) for b in sellers]

total_buy = int(float(total_buy_match.group(1).replace(',', '')) * 1000)
total_sell = int(float(total_sell_match.group(1).replace(',', '')) * 1000)

stock_data = {
    'summary': {'total_buy': total_buy, 'total_sell': total_sell, 'net': total_buy - total_sell},
    'top_buy': top_buy,
    'top_sell': top_sell
}

data = json.load(open('data/brokers/20260806.json', encoding='utf-8'))
data['stocks']['8299'] = stock_data
with open('data/brokers/20260806.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
print('8299 patched!')
