from bs4 import BeautifulSoup
import json
with open(r'C:\Users\user\.gemini\antigravity\brain\7225002b-5613-489d-9293-1b6414d8bb69\.system_generated\steps\3124\content.md', 'r', encoding='utf-8') as f:
    html = f.read()
soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('li', class_='List(n)')
print("Found List(n) rows:", len(rows))
for row in rows[:5]:
    cols = [d.text.strip() for d in row.find_all('div') if d.text.strip()]
    if cols:
        print(cols)
