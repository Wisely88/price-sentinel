"""
PriceSentinel Configuration Module / 配置模块
Defines global directories, server binding, database paths, and networking settings.
定义全局目录、服务绑定端口、数据库路径以及网络请求参数。
"""

import os
from pathlib import Path

# Base directories / 基础目录
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database file path / 数据库文件路径
DB_PATH = DATA_DIR / "sentinel.db"

# Server configuration / Web 服务配置
HOST = os.getenv("SENTINEL_HOST", "0.0.0.0")
PORT = int(os.getenv("SENTINEL_PORT", "8765"))

# Background sentinel scheduler default interval (hours) / 后台哨兵定时巡检默认间隔（小时）
DEFAULT_CHECK_INTERVAL_HOURS = 4

# HTTP Client network timeout (seconds) / 网络请求超时时间（秒）
DEFAULT_TIMEOUT = 10.0

# User-Agent header for scraping / 请求伪装 User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
