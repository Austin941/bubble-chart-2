import requests, urllib3
urllib3.disable_warnings()

headers = {'User-Agent': 'Mozilla/5.0'}

r1 = requests.get('https://tw.stock.yahoo.com/quote/8299/broker-trading', headers=headers, verify=False)
print('8299 found:', 'buyerRankList' in r1.text)

r2 = requests.get('https://tw.stock.yahoo.com/quote/8299.TWO/broker-trading', headers=headers, verify=False)
print('8299.TWO found:', 'buyerRankList' in r2.text)
