#!/usr/bin/env python3
"""
PriceSentinel Server Launcher / 启动入口
Boots the FastAPI application with Uvicorn, detects LAN IP for mobile testing,
and displays active features.
使用 Uvicorn 启动 FastAPI 应用程序，检测局域网 IP 以便手机真机访问，并展示运行状态。
"""

import sys
import socket
import uvicorn
from pathlib import Path

# Add project root to sys.path / 将项目根目录添加至 Python 模块搜索路径
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import HOST, PORT

def get_local_ip() -> str:
    """
    Get LAN IP address for mobile device access.
    获取本机局域网 IP 地址，便于手机与平板在同一 Wi-Fi 下直接访问。
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def print_banner(host: str, port: int, lan_ip: str):
    """
    Display start banner and access URLs.
    打印启动横幅与终端访问地址。
    """
    banner = f"""
====================================================================
           PriceSentinel · 纯净全网比价与降价提醒平台
      Ad-Free Cross-Platform Price Comparison & Sentinel
====================================================================
  [✓] 广告剥离引擎 / Ad Stripping:    已启用 (过滤推广/配件/非国行陷阱)
  [✓] 渠道覆盖范围 / Platforms:       京东自营 / 淘宝天猫 / 拼多多百亿补贴
  [✓] 自动巡检推送 / Push Notifier:   已常驻 (macOS 通知 / Bark / Webhook)
--------------------------------------------------------------------
  本机访问地址 (Localhost):        http://127.0.0.1:{port}
  局域网手机访问 (LAN Mobile):     http://{lan_ip}:{port}
====================================================================
    """
    print(banner)

def main():
    lan_ip = get_local_ip()
    print_banner(HOST, PORT, lan_ip)
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info", access_log=False)

if __name__ == "__main__":
    main()
