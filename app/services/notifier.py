"""
Multi-Channel Notification Dispatcher / 多通道告警通知分发器
Supports native macOS desktop notifications, iOS Bark push, and generic Webhooks.
支持 macOS 原生桌面弹窗通知、iOS 移动端 Bark 实时推送及通用 Webhook（企微/飞书/钉钉）机器人分发。
"""

import subprocess
import httpx
from typing import Optional, Dict, Any
from app.database import get_setting

class NotifierService:

    @staticmethod
    def send_mac_notification(title: str, message: str, url: Optional[str] = None) -> bool:
        """
        Send a native macOS notification banner via osascript.
        Safe against quotes and special characters.
        """
        try:
            clean_title = title.replace('"', '\\"')
            clean_msg = message.replace('"', '\\"')
            script = f'display notification "{clean_msg}" with title "PriceSentinel 价格哨兵" subtitle "{clean_title}" sound name "Glass"'
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, timeout=3)
            return True
        except Exception as e:
            print(f"[Notifier] macOS notification error: {e}")
            return False

    @staticmethod
    async def send_bark_notification(bark_key: str, title: str, body: str, url: Optional[str] = None) -> bool:
        """
        Send push notification to iPhone via Bark.
        Clicking the notification can directly open the item URL.
        """
        if not bark_key.strip():
            return False
        
        # Clean bark key if user pasted whole url
        key = bark_key.strip().rstrip("/")
        if "/" in key:
            key = key.split("/")[-1]

        endpoint = f"https://api.day.app/{key}"
        payload = {
            "title": f"降价提醒: {title}",
            "body": body,
            "group": "PriceSentinel",
            "icon": "https://img.icons8.com/color/96/shopping-bag.png",
            "sound": "anticipate"
        }
        if url:
            payload["url"] = url

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(endpoint, json=payload)
                return res.status_code == 200
        except Exception as e:
            print(f"[Notifier] Bark error: {e}")
            return False

    @staticmethod
    async def send_webhook(webhook_url: str, title: str, body: str, url: Optional[str] = None) -> bool:
        """
        Send notification to generic webhook (Feishu / DingTalk / WeCom / ServerChan).
        """
        if not webhook_url.strip():
            return False

        payload: Dict[str, Any] = {}
        # ServerChan format
        if "sctapi.ftqq.com" in webhook_url or "sc.ftqq.com" in webhook_url:
            payload = {
                "title": f"【降价提醒】{title}",
                "desp": f"{body}\n\n[点击前往查看直达链接]({url or ''})"
            }
        # Feishu format
        elif "open.feishu.cn" in webhook_url:
            payload = {
                "msg_type": "text",
                "content": {"text": f"【降价提醒】{title}\n{body}\n链接: {url or ''}"}
            }
        # DingTalk / WeCom / Default
        else:
            payload = {
                "msgtype": "text",
                "text": {"content": f"【降价提醒】{title}\n{body}\n链接: {url or ''}"}
            }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(webhook_url.strip(), json=payload)
                return res.status_code == 200
        except Exception as e:
            print(f"[Notifier] Webhook error: {e}")
            return False

    @classmethod
    async def notify_all(cls, title: str, body: str, url: Optional[str] = None) -> Dict[str, bool]:
        """
        Dispatch notification to all configured channels.
        """
        results = {}
        enable_mac = get_setting("enable_mac_notify", "1") == "1"
        bark_key = get_setting("bark_key", "")
        webhook_url = get_setting("webhook_url", "")

        if enable_mac:
            results["mac"] = cls.send_mac_notification(title, body, url)

        if bark_key:
            results["bark"] = await cls.send_bark_notification(bark_key, title, body, url)

        if webhook_url:
            results["webhook"] = await cls.send_webhook(webhook_url, title, body, url)

        return results
