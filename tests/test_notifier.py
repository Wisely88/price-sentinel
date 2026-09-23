import pytest
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.notifier import NotifierService

def test_mac_notification():
    # Test that osascript notification doesn't raise exception
    res = NotifierService.send_mac_notification(
        title="PriceSentinel 测试",
        message="单测通知验证已触发",
        url="http://127.0.0.1:8765"
    )
    # On mac, osascript returns True
    assert res is True

def test_bark_notification_validation():
    # If key is empty, should safely return False without error
    res = asyncio.run(NotifierService.send_bark_notification("", "Title", "Body"))
    assert res is False

def test_webhook_validation():
    # If webhook is empty, should safely return False without error
    res = asyncio.run(NotifierService.send_webhook("", "Title", "Body"))
    assert res is False
