"""
泡泡圖 2.0 — 自動更新目錄索引 (index.json)
掃描 data/holders 和 data/brokers 資料夾中的 JSON，
自動更新 data/index.json 提供前端讀取。
"""
import sys, json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
INDEX_PATH = DATA_DIR / "index.json"

def get_dates(folder_name):
    folder = DATA_DIR / folder_name
    if not folder.exists():
        return []
    # 找所有的 .json 檔 (排除 .gitkeep 等)
    files = [f.stem for f in folder.glob("*.json") if f.stem.isdigit()]
    # 降序排序，最新日期在前面
    return sorted(files, reverse=True)

def main():
    holders = get_dates("holders")
    brokers = get_dates("brokers")

    index_data = {
        "holders": holders,
        "brokers": brokers,
        "last_updated": datetime.now().isoformat()
    }

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    print(f"✅ index.json 更新完成！ (大戶: {len(holders)} 天, 分點: {len(brokers)} 天)")

if __name__ == "__main__":
    main()
