"""
泡泡圖 2.0 — 全域設定
"""
from pathlib import Path

# ── 路徑 ─────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
HOLDERS_DIR = DATA_DIR / "holders"
BROKERS_DIR = DATA_DIR / "brokers"
META_DIR = DATA_DIR / "meta"
BRANCHES_DIR = DATA_DIR / "branches"

for _d in (HOLDERS_DIR, BROKERS_DIR, META_DIR, BRANCHES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── TDCC API ─────────────────────────────────────────────
TDCC_CSV_URL = "https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5"

# 持股分級定義（集保官方 15 個級距）
HOLDER_LEVELS = {
    1:  "1~999 股（未滿 1 張）",
    2:  "1,000~5,000 股（1~5 張）",
    3:  "5,001~10,000 股（5~10 張）",
    4:  "10,001~15,000 股（10~15 張）",
    5:  "15,001~20,000 股（15~20 張）",
    6:  "20,001~30,000 股（20~30 張）",
    7:  "30,001~40,000 股（30~40 張）",
    8:  "40,001~50,000 股（40~50 張）",
    9:  "50,001~100,000 股（50~100 張）",
    10: "100,001~200,000 股（100~200 張）",
    11: "200,001~400,000 股（200~400 張）",
    12: "400,001~600,000 股（400~600 張）",
    13: "600,001~800,000 股（600~800 張）",
    14: "800,001~1,000,000 股（800~1000 張）",
    15: "1,000,001 股以上（千張大戶）",
}
WHALE_LEVEL = 15          # 千張大戶
RETAIL_LEVELS = {1, 2, 3} # 散戶（10 張以下）
MID_LEVELS = {4, 5, 6, 7, 8, 9}  # 中小戶

# ── FinMind API ──────────────────────────────────────────
FINMIND_BASE = "https://api.finmindtrade.com/api/v4"
FINMIND_DATA_URL = f"{FINMIND_BASE}/data"
FINMIND_STORAGE_URL = f"{FINMIND_BASE}/storage_objects"

DATASET_HOLDERS = "TaiwanStockHoldingSharesPer"
DATASET_BROKERS = "TaiwanStockTradingDailyReport"

# ── TWSE OpenAPI ─────────────────────────────────────────
TWSE_OPENAPI_BASE = "https://openapi.twse.com.tw/v1"
TWSE_STOCK_LIST_URL = f"{TWSE_OPENAPI_BASE}/exchangeReport/STOCK_DAY_AVG_ALL"

# ── 抓取參數 ─────────────────────────────────────────────
TOP_BROKER_N = 20       # 每支股票保留前 N 大分點
REQUEST_TIMEOUT = 60    # 秒
RETRY_ATTEMPTS = 3
RETRY_DELAY = 10        # 秒
BACKFILL_SLEEP = 2      # 批次補抓的間隔秒數（避免過載）
