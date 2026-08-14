import json
from pathlib import Path

data_dir = Path('data/holders/history')
count = 0
for file in data_dir.glob('*.json'):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        modified = False
        for item in data:
            w = item.get('whale_pct') if 'whale_pct' in item else item.get('whale', 0.0)
            r = item.get('retail_pct') if 'retail_pct' in item else item.get('retail', 0.0)
            
            if r == 0.0 and w > 0.0:
                new_r = round(100.0 - w, 2)
                if 'retail_pct' in item:
                    item['retail_pct'] = new_r
                else:
                    item['retail'] = new_r
                    
                # Fix big_vs_retail diff
                diff = round(w - new_r, 4)
                if 'big_vs_retail' in item:
                    item['big_vs_retail'] = diff
                modified = True
        
        if modified:
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
            count += 1
            print(f"Fixed {file.name}")
    except Exception as e:
        print(f"Error processing {file.name}: {e}")

print(f"Fixed {count} files.")
