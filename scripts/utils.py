"""
泡泡圖 2.0 — 共用工具函式
retry、logging、git push、HTTP helpers
"""
import time, logging, os, json, subprocess
from pathlib import Path
from functools import wraps
from datetime import datetime

# ── Logging 設定 ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("bubble")

# ── Retry Decorator ──────────────────────────────────────
def retry(max_attempts: int = 3, delay: int = 10):
    """遇到例外自動重試"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt < max_attempts:
                        log.warning(f"[{func.__name__}] 第 {attempt} 次失敗：{e}，{delay}s 後重試…")
                        time.sleep(delay)
                    else:
                        log.error(f"[{func.__name__}] 已達最大重試次數，放棄。")
            raise last_err
        return wrapper
    return decorator

# ── 檔案 I/O ─────────────────────────────────────────────
def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    log.info(f"✅ 儲存：{path}  ({path.stat().st_size/1024:.1f} KB)")

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def already_exists(path: Path) -> bool:
    """避免重複下載相同日期的資料"""
    if path.exists() and path.stat().st_size > 100:
        log.info(f"⏭  跳過（已存在）：{path.name}")
        return True
    return False

# ── HTTP ─────────────────────────────────────────────────
def get_request_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
    }

# ── Git 自動推送 ─────────────────────────────────────────
def git_commit_push(message: str) -> None:
    """在 GitHub Actions 環境中自動 commit & push"""
    if not os.environ.get("GITHUB_ACTIONS"):
        log.info("非 CI 環境，跳過 git push")
        return
    cmds = [
        ["git", "config", "user.name", "Data Bot 🤖"],
        ["git", "config", "user.email", "bot@noreply.github.com"],
        ["git", "add", "data/"],
    ]
    for cmd in cmds:
        subprocess.run(cmd, check=True)
    diff = subprocess.run(["git", "diff", "--staged", "--quiet"])
    if diff.returncode == 0:
        log.info("沒有新資料，不 commit")
        return
    subprocess.run(["git", "commit", "-m", message], check=True)
    subprocess.run(["git", "push"], check=True)
    log.info(f"🚀 Git push 成功：{message}")

# ── 時間工具 ─────────────────────────────────────────────
def today_str() -> str:
    return datetime.now().strftime("%Y%m%d")

def ts() -> str:
    return datetime.now().isoformat()
