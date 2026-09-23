#!/usr/bin/env python3
import sys
import socket
import uvicorn
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from config import HOST, PORT

def get_local_ip():
    """Get LAN IP address for mobile device access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def print_banner(host, port, lan_ip):
    banner = f"""
====================================================================
           PriceSentinel · 纯净全网比价与降价提醒平台
====================================================================
  [✓] 广告剥离引擎: 已启用 (自动过滤 HOT / 直通车 / 配件陷阱)
  [✓] 渠道覆盖范围: 京东自营 / 淘宝天猫 / 拼多多百亿补贴
  [✓] 自动巡检推送: 已常驻 (macOS 原生通知 / iOS Bark / Webhook)
--------------------------------------------------------------------
  本机访问地址:   http://127.0.0.1:{port}
  局域网手机访问: http://{lan_ip}:{port}
====================================================================
    """
    print(banner)

def main():
    lan_ip = get_local_ip()
    print_banner(HOST, PORT, lan_ip)
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="info", access_log=False)

if __name__ == "__main__":
    main()
